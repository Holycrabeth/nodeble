"""NODEBLE CLI — Iron Condor trading automation.

Usage:
    python -m nodeble --mode signal [--force]
    python -m nodeble --mode scan [--dry-run] [--force]
    python -m nodeble --mode manage [--dry-run] [--force]
    python -m nodeble --test-broker
    python -m nodeble --validate-config
"""
import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from nodeble.paths import get_data_dir, get_config_dir
from nodeble.core.state import SpreadState
from nodeble.core import risk as options_risk
from nodeble.core.audit import log_event
from nodeble.core.calendar import is_market_open
from nodeble.strategy.factory import scan_for_condors
from nodeble.strategy.executor import SpreadExecutor
from nodeble.strategy.manager import (
    cleanup_stale_orders, verify_pending_fills, evaluate_positions,
)
from nodeble.signals.signal_job import run_signal_job, read_signal_state
from nodeble.strategy.adaptive import compute_adaptive_params

logger = logging.getLogger("nodeble")
NY = ZoneInfo("America/New_York")


def setup_logging():
    log_dir = get_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_dir / "nodeble.log"),
        ],
    )


def load_config(name: str) -> dict:
    path = get_config_dir() / name
    if not path.exists():
        logger.error(f"Config not found: {path}")
        sys.exit(1)
    return yaml.safe_load(path.read_text())


def load_broker():
    """Lazy-load TigerBroker to avoid importing tigeropen at module level."""
    try:
        from nodeble.core.tiger_broker import TigerBroker
        broker_cfg = load_config("broker.yaml")
        return TigerBroker(broker_cfg)
    except Exception as e:
        logger.error(f"Failed to initialize broker: {e}")
        return None


def _ping_health_check(strategy_cfg: dict):
    """Ping healthchecks.io to confirm bot is running. Fire-and-forget."""
    url = strategy_cfg.get("health_check_url")
    if not url:
        return
    try:
        import requests
        requests.get(url, timeout=5)
        logger.debug(f"Health check pinged: {url}")
    except Exception as e:
        logger.warning(f"Health check ping failed (non-blocking): {e}")


def load_notifier():
    try:
        from nodeble.notify.telegram import TelegramNotifier
        notify_cfg = load_config("notify.yaml")
        tg_cfg = notify_cfg.get("telegram", {})
        return TelegramNotifier(
            bot_token=tg_cfg.get("bot_token", ""),
            chat_id=str(tg_cfg.get("chat_id", "")),
            enabled=tg_cfg.get("enabled", False),
        )
    except Exception:
        logger.warning("Telegram notifier not configured, running without notifications")
        return None


def test_broker():
    """Test broker connection and display account info."""
    broker = load_broker()
    if broker is None:
        print("FAIL: Could not connect to broker")
        sys.exit(1)
    try:
        assets = broker.get_assets()
        seg = assets.segments["S"]
        print(f"OK: Connected to Tiger Brokers")
        print(f"  Cash available: ${seg.cash_available_for_trade:,.2f}")
        print(f"  Net liquidation: ${seg.net_liquidation:,.2f}")
    except Exception as e:
        print(f"FAIL: {e}")
        sys.exit(1)


def run_scan(broker, notifier, state, state_path, risk_cfg, strategy_cfg, dry_run):
    if not options_risk.check_kill_switch(risk_cfg):
        logger.warning("Kill switch is ON — aborting scan")
        return []

    candidates, rejections = scan_for_condors(
        broker=broker, state=state, risk_cfg=risk_cfg,
        strategy_cfg=strategy_cfg, dry_run=dry_run,
    )

    if not candidates:
        logger.info(f"No candidates found ({len(rejections)} rejections)")
        return []

    executor = SpreadExecutor(
        broker=broker, notifier=notifier, config=strategy_cfg,
        state=state, state_path=state_path,
    )

    results = []
    for candidate in candidates:
        if not options_risk.check_max_spreads(state, risk_cfg):
            break
        if not options_risk.check_total_exposure(state, risk_cfg, candidate.max_risk * candidate.contracts * 100):
            continue

        result = executor.execute_iron_condor(candidate, dry_run=dry_run)
        results.append(result)
        log_event("condor", "execution", **result)

    return results


def run_manage(broker, notifier, state, state_path, risk_cfg, strategy_cfg, dry_run, vix=None):
    cleanup_stale_orders(broker=broker, state=state)
    verify_pending_fills(broker=broker, state=state)

    actions = evaluate_positions(
        state=state, broker=broker, strategy_cfg=strategy_cfg,
        vix=vix,
    )

    if not actions:
        logger.info("No management actions needed")
        return []

    executor = SpreadExecutor(
        broker=broker, notifier=notifier, config=strategy_cfg,
        state=state, state_path=state_path,
    )

    results = []
    for action in actions:
        result = executor.close_spread(action.position, dry_run=dry_run)
        results.append(result)
        log_event("condor", "close", **result)

    return results


def run_signal(notifier, strategy_cfg):
    """Run signal generation job and send Telegram summary."""
    watchlist = strategy_cfg.get("watchlist", [])
    if not watchlist:
        logger.warning("Empty watchlist — nothing to signal")
        return

    state = run_signal_job(watchlist, strategy_cfg)

    # Telegram summary
    if notifier:
        vix_str = f"VIX {state['vix']:.1f}" if state["vix"] else "VIX unavailable"
        vix9d_str = f", VIX9D {state.get('vix9d', 0):.1f}" if state.get("vix9d") else ""
        term_str = f", {state['term_structure']} {state['term_ratio']:.2f}x" if state.get("term_ratio") else ""
        lines = [f"Signal Update ({vix_str}{vix9d_str}{term_str}):"]
        for sym, sig in state["symbols"].items():
            direction = "bearish" if sig["bull_share"] < 0.45 else "bullish" if sig["bull_share"] > 0.55 else "neutral"
            lines.append(f"{sym}: {direction} (bull {sig['bull_share']:.0%}, {sig['active_count']}/20)")
        notifier.send("\n".join(lines))


def _apply_adaptive_params(strategy_cfg, notifier):
    """Read signal state and apply adaptive parameters to strategy config."""
    signal_state = read_signal_state()
    adaptive_cfg = strategy_cfg.get("adaptive", {})

    if not adaptive_cfg:
        return

    if signal_state is None:
        logger.warning("Signal data unavailable, using fallback defaults")
        if notifier:
            notifier.send("WARNING: Signal data unavailable, IC scan using fallback defaults. Check signal job.")
        sel = strategy_cfg.get("selection", {})
        adjusted = compute_adaptive_params(0.50, None, sel, adaptive_cfg, term_ratio=None)
        strategy_cfg["selection"].update(adjusted)
        logger.info("Adaptive params applied with fallback defaults (no signal data)")
        return

    # Compute average bull_share across all symbols
    symbols_data = signal_state.get("symbols", {})
    if symbols_data:
        avg_bull_share = sum(s["bull_share"] for s in symbols_data.values()) / len(symbols_data)
    else:
        avg_bull_share = 0.50

    vix = signal_state.get("vix")
    term_ratio = signal_state.get("term_ratio")
    sel = strategy_cfg.get("selection", {})
    adjusted = compute_adaptive_params(avg_bull_share, vix, sel, adaptive_cfg, term_ratio=term_ratio)

    # Overwrite selection with adjusted values
    strategy_cfg["selection"].update(adjusted)

    logger.info(
        f"Adaptive params applied: VIX={vix}, bull_share={avg_bull_share:.2f}, "
        f"put_delta=[{adjusted['put_delta_min']:.3f}-{adjusted['put_delta_max']:.3f}], "
        f"call_delta=[{adjusted['call_delta_min']:.3f}-{adjusted['call_delta_max']:.3f}], "
        f"DTE=[{adjusted['dte_min']}-{adjusted['dte_max']}]"
    )


def main():
    parser = argparse.ArgumentParser(description="NODEBLE Iron Condor Automation")
    parser.add_argument("--mode", choices=["scan", "manage", "signal", "backtest"], help="Run mode")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without placing orders")
    parser.add_argument("--force", action="store_true", help="Bypass dedup guard")
    parser.add_argument("--test-broker", action="store_true", help="Test broker connection")
    parser.add_argument("--validate-config", action="store_true", help="Validate config files")
    parser.add_argument("--sweep", action="store_true", help="Run parameter sweep (backtest)")
    parser.add_argument("--analyze", action="store_true", help="Run feature importance (backtest)")
    parser.add_argument("--symbols", default="SPY,QQQ,IWM", help="Symbols for backtest")
    parser.add_argument("--years", type=int, default=5, help="Years of history (backtest)")
    parser.add_argument("--force-fetch", action="store_true", help="Re-download data (backtest)")
    args = parser.parse_args()

    setup_logging()

    if args.test_broker:
        test_broker()
        return

    if not args.mode:
        parser.print_help()
        sys.exit(1)

    # Load configs
    strategy_cfg = load_config("strategy.yaml")

    # Signal mode — runs independently, no broker/state needed
    if args.mode == "signal":
        notifier = load_notifier()
        run_signal(notifier, strategy_cfg)
        _ping_health_check(strategy_cfg)
        return

    # Backtest mode — runs independently
    if args.mode == "backtest":
        from nodeble.backtest.runner import run_backtest
        symbols = [s.strip() for s in args.symbols.split(",")]
        run_backtest(
            symbols=symbols,
            years=args.years,
            force_fetch=args.force_fetch,
            do_sweep=args.sweep,
            do_analyze=args.analyze,
            strategy_cfg=strategy_cfg,
        )
        return

    risk_cfg = options_risk.load_risk_config(str(get_config_dir() / "risk.yaml"))

    # Force dry-run if config says so
    dry_run = args.dry_run
    if strategy_cfg.get("mode") == "dry_run":
        dry_run = True

    # Load state
    data_dir = get_data_dir() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    state_path = str(data_dir / "state.json")
    state = SpreadState.load(state_path)

    # Dedup guard
    today = date.today().isoformat()
    if args.mode == "scan" and state.last_scan_date == today and not args.force:
        logger.info("Already scanned today. Use --force to override.")
        return
    if args.mode == "manage" and state.last_manage_date == today and not args.force:
        logger.info("Already managed today. Use --force to override.")
        return

    # Market hours advisory
    if not is_market_open():
        logger.info("Market is closed (advisory — proceeding anyway for scan)")

    # Init broker + notifier
    broker = None if dry_run else load_broker()
    notifier = load_notifier()

    # Apply adaptive parameters before scan
    if args.mode == "scan":
        _apply_adaptive_params(strategy_cfg, notifier)

    # Run
    if args.mode == "scan":
        results = run_scan(broker, notifier, state, state_path, risk_cfg, strategy_cfg, dry_run)
        if not dry_run:
            state.last_scan_date = today
            state.save(state_path)
    else:
        from nodeble.data.vix import get_vix as fetch_manage_vix
        manage_vix = fetch_manage_vix()
        if manage_vix is None:
            logger.warning("VIX unavailable for dynamic profit targets, using defaults")
            if notifier:
                notifier.send("WARNING: VIX unavailable for profit targets, using 50% default.")
        results = run_manage(broker, notifier, state, state_path, risk_cfg, strategy_cfg, dry_run, vix=manage_vix)
        if not dry_run:
            state.last_manage_date = today
            state.save(state_path)

    # Save signals/executions
    signals_dir = data_dir / "signals"
    signals_dir.mkdir(exist_ok=True)
    exec_dir = data_dir / "executions"
    exec_dir.mkdir(exist_ok=True)
    out_dir = signals_dir if args.mode == "scan" else exec_dir
    out_path = out_dir / f"{args.mode}_{today}.json"
    out_path.write_text(json.dumps(results, default=str, indent=2))

    # Ping health check (fire-and-forget, never blocks trading)
    _ping_health_check(strategy_cfg)

    # Summary
    print(f"\n{'='*40}")
    print(f"Mode: {args.mode} | Dry-run: {dry_run}")
    print(f"Results: {len(results)} actions")
    print(f"Open positions: {len(state.get_open_positions())}")
    print(f"{'='*40}")


if __name__ == "__main__":
    main()
