# -*- coding: utf-8 -*-
"""VIX utilities for options strategy scaling."""

import copy
import logging

import yfinance as yf

logger = logging.getLogger(__name__)


def get_vix() -> float | None:
    """Fetch current VIX level. Returns None on failure (callers decide fail-open/closed)."""
    try:
        ticker = yf.Ticker("^VIX")
        try:
            price = ticker.fast_info.last_price
            if price and price > 0:
                return float(price)
        except Exception:
            pass

        hist = ticker.history(period="1d")
        if hist is not None and not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception as e:
        logger.warning(f"Failed to fetch VIX: {e}")

    return None


def get_vix9d() -> float | None:
    """Fetch current VIX9D (9-day implied vol). Returns None on failure."""
    try:
        ticker = yf.Ticker("^VIX9D")
        try:
            price = ticker.fast_info.last_price
            if price and price > 0:
                return float(price)
        except Exception:
            pass

        hist = ticker.history(period="1d")
        if hist is not None and not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception as e:
        logger.warning(f"Failed to fetch VIX9D: {e}")

    return None


def apply_vix_overrides(base_cfg: dict, vix: float | None, scaling_cfg: dict) -> dict:
    """Apply VIX-tier overrides to a config dict. Returns modified copy."""
    if not scaling_cfg.get("enabled", False):
        return base_cfg

    if vix is None:
        logger.info("VIX unavailable — no scaling applied")
        return base_cfg

    tiers = scaling_cfg.get("tiers", [])

    for tier in tiers:
        matched = False
        if "vix_above" in tier and vix > tier["vix_above"]:
            matched = True
        if "vix_below" in tier and vix < tier["vix_below"]:
            matched = True

        if matched:
            result = copy.deepcopy(base_cfg)
            overrides_applied = []
            for key, value in tier.items():
                if key in ("vix_above", "vix_below"):
                    continue
                if key.endswith("_override"):
                    target_key = key[:-9]
                    result[target_key] = value
                    overrides_applied.append(f"{target_key}={value}")

            tier_desc = f"vix_above={tier['vix_above']}" if "vix_above" in tier else f"vix_below={tier['vix_below']}"
            logger.info(f"VIX={vix:.1f} matched tier [{tier_desc}]: {', '.join(overrides_applied)}")
            return result

    logger.info(f"VIX={vix:.1f} — no tier matched, using defaults")
    return base_cfg
