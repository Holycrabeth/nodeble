"""NODEBLE CLI — Iron Condor trading automation.

Usage:
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


def run_manage(broker, notifier, state, state_path, risk_cfg, strategy_cfg, dry_run):
    cleanup_stale_orders(broker=broker, state=state)
    verify_pending_fills(broker=broker, state=state)

    actions = evaluate_positions(
        state=state, broker=broker, strategy_cfg=strategy_cfg,
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


def main():
    parser = argparse.ArgumentParser(description="NODEBLE Iron Condor Automation")
    parser.add_argument("--mode", choices=["scan", "manage"], help="Run mode")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without placing orders")
    parser.add_argument("--force", action="store_true", help="Bypass dedup guard")
    parser.add_argument("--test-broker", action="store_true", help="Test broker connection")
    parser.add_argument("--validate-config", action="store_true", help="Validate config files")
    args = parser.parse_args()

    setup_logging()

    if args.test_broker:
        test_broker()
        return

    if not args.mode:
        parser.print_help()
        sys.exit(1)

    # Load configs
    risk_cfg = options_risk.load_risk_config(str(get_config_dir() / "risk.yaml"))
    strategy_cfg = load_config("strategy.yaml")

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

    # Run
    if args.mode == "scan":
        results = run_scan(broker, notifier, state, state_path, risk_cfg, strategy_cfg, dry_run)
        if not dry_run:
            state.last_scan_date = today
            state.save(state_path)
    else:
        results = run_manage(broker, notifier, state, state_path, risk_cfg, strategy_cfg, dry_run)
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

    # Summary
    print(f"\n{'='*40}")
    print(f"Mode: {args.mode} | Dry-run: {dry_run}")
    print(f"Results: {len(results)} actions")
    print(f"Open positions: {len(state.get_open_positions())}")
    print(f"{'='*40}")


if __name__ == "__main__":
    main()
