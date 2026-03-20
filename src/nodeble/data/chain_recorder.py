# -*- coding: utf-8 -*-
"""Options chain snapshot recorder for future backtesting.

Saves raw chain data fetched during scan jobs. Zero extra API calls —
just persists what scanners already fetch.
"""

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path

from nodeble.paths import get_data_dir

logger = logging.getLogger(__name__)


def _serialize_chain_item(item) -> dict:
    """Convert a chain item (dict or SDK object) to a plain dict."""
    if isinstance(item, dict):
        return item
    fields = [
        "identifier", "strike", "put_call", "right",
        "bid_price", "ask_price", "delta", "gamma", "theta", "vega",
        "implied_vol", "implied_volatility", "open_interest", "volume",
        "latest_price",
    ]
    out = {}
    for f in fields:
        val = getattr(item, f, None)
        if val is not None:
            out[f] = val
    return out


def record_chain_snapshot(
    symbol: str,
    expiry: str,
    chain_data: list,
    stock_price: float = 0.0,
    iv_rank: float = 0.0,
    iv_rv_ratio: float = 0.0,
    source: str = "unknown",
) -> Path | None:
    """Save a raw chain snapshot to disk. Never blocks trading on failure."""
    try:
        snapshot_dir = get_data_dir() / "data" / "chain_snapshots"
        today_str = date.today().isoformat()
        day_dir = snapshot_dir / today_str
        day_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{symbol}_{expiry}_{source}.json"
        filepath = day_dir / filename

        serialized = [_serialize_chain_item(item) for item in chain_data]

        snapshot = {
            "symbol": symbol,
            "expiry": expiry,
            "source": source,
            "stock_price": stock_price,
            "iv_rank": iv_rank,
            "iv_rv_ratio": iv_rv_ratio,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "chain_count": len(serialized),
            "chain": serialized,
        }

        with open(filepath, "w") as f:
            json.dump(snapshot, f, default=str)

        logger.debug(f"Recorded chain snapshot: {filepath} ({len(serialized)} strikes)")
        return filepath

    except Exception as e:
        logger.warning(f"Chain recording failed for {symbol}/{expiry}/{source}: {e}")
        return None
