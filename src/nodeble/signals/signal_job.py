# -*- coding: utf-8 -*-
"""Signal generation job: fetch OHLCV, run 20 indicators, fetch VIX, write state."""
import json
import logging
import os
import tempfile
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from nodeble.paths import get_data_dir, get_config_dir
from nodeble.data.fetcher import DataFetcher
from nodeble.data.vix import get_vix
from nodeble.signals.registry import get_all_indicators, get_max_warmup
from nodeble.signals.scorer import VotingEngine, load_voting_config

logger = logging.getLogger(__name__)

NY = ZoneInfo("America/New_York")
SIGNAL_STATE_FILE = "signal_state.json"
STALENESS_HOURS = 24


def write_signal_state(state: dict, path: str = None):
    """Atomic write signal state to JSON file."""
    if path is None:
        data_dir = get_data_dir() / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        path = str(data_dir / SIGNAL_STATE_FILE)

    dir_name = os.path.dirname(path)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f, indent=2, default=str)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def read_signal_state(path: str = None) -> dict | None:
    """Read signal state. Returns None if missing or stale (>24h)."""
    if path is None:
        path = str(get_data_dir() / "data" / SIGNAL_STATE_FILE)

    try:
        with open(path, "r") as f:
            state = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning(f"Signal state file missing or corrupt: {path}")
        return None

    # Check staleness
    generated_at = state.get("generated_at")
    if generated_at:
        try:
            gen_time = datetime.fromisoformat(generated_at)
            now = datetime.now(NY)
            if (now - gen_time) > timedelta(hours=STALENESS_HOURS):
                logger.warning(
                    f"Signal state is stale (generated {generated_at}, "
                    f">{STALENESS_HOURS}h ago)"
                )
                return None
        except (ValueError, TypeError):
            logger.warning(f"Invalid generated_at in signal state: {generated_at}")
            return None

    return state


def _determine_vix_tier(vix: float | None, adaptive_cfg: dict) -> str:
    """Return human-readable VIX tier string."""
    if vix is None:
        return "unavailable"
    tiers = adaptive_cfg.get("vix_tiers", [])
    prev_max = 0
    for tier in sorted(tiers, key=lambda t: t["max_vix"]):
        if vix <= tier["max_vix"]:
            if tier["max_vix"] >= 999:
                return f"{prev_max}+"
            return f"{prev_max}-{tier['max_vix']}"
        prev_max = tier["max_vix"]
    return "unknown"


def run_signal_job(watchlist: list[str], strategy_cfg: dict) -> dict:
    """Run the full signal generation pipeline.

    1. Fetch 252-day OHLCV per symbol
    2. Run 20 indicators -> VotingEngine -> bull_share per symbol
    3. Fetch VIX
    4. Write signal_state.json

    Returns the signal state dict.
    """
    signals_cfg_path = str(get_config_dir() / "signals.yaml")
    indicators = get_all_indicators(signals_cfg_path)
    voting_config = load_voting_config(signals_cfg_path)
    engine = VotingEngine(config=voting_config)

    warmup = get_max_warmup()
    lookback_days = max(warmup + 50, 300)

    fetcher = DataFetcher()  # yfinance only (no broker needed for signals)
    today = date.today()
    start = today - timedelta(days=int(lookback_days * 1.5))  # Account for weekends/holidays

    # Fetch OHLCV
    bars = fetcher.get_daily_bars_batch(watchlist, start, today)

    # Score each symbol
    symbol_signals = {}
    for symbol in watchlist:
        df = bars.get(symbol)
        if df is None or df.empty:
            logger.warning(f"No OHLCV data for {symbol} — skipping signal")
            continue

        result = engine.score(symbol, df, indicators)
        symbol_signals[symbol] = {
            "bull_share": result.bull_share,
            "decision": result.decision,
            "confidence": result.confidence,
            "bull_count": result.bull_count,
            "bear_count": result.bear_count,
            "active_count": result.active_count,
            "active_ratio": result.active_ratio,
            "votes": result.votes,
        }

    # Fetch VIX
    vix = get_vix()
    vix_fallback = vix is None
    if vix_fallback:
        logger.warning("VIX unavailable — signal state will indicate fallback")

    adaptive_cfg = strategy_cfg.get("adaptive", {})
    vix_tier = _determine_vix_tier(vix, adaptive_cfg)

    # Build state
    now = datetime.now(NY)
    state = {
        "version": 1,
        "generated_at": now.isoformat(),
        "vix": vix,
        "vix_tier": vix_tier,
        "vix_fallback": vix_fallback,
        "symbols": symbol_signals,
    }

    write_signal_state(state)
    logger.info(f"Signal state written: {len(symbol_signals)} symbols, VIX={vix}")
    return state
