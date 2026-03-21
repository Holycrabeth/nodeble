# -*- coding: utf-8 -*-
"""Adaptive parameter computation for iron condor strategy.

Pure function: signal state + VIX + base config -> adjusted delta/DTE params.
No side effects, no I/O, no broker calls.
"""
import logging

logger = logging.getLogger(__name__)

# Fallback tier when VIX is unavailable (15-20 range = standard posture)
_FALLBACK_TIER = {"max_vix": 20, "delta_scale": 1.00, "dte_min": 12, "dte_max": 25}


def _get_vix_tier(vix: float | None, tiers: list[dict]) -> dict:
    """Match VIX to the first tier where vix <= max_vix."""
    if vix is None:
        logger.warning("VIX unavailable — using fallback tier (15-20)")
        return _FALLBACK_TIER

    for tier in sorted(tiers, key=lambda t: t["max_vix"]):
        if vix <= tier["max_vix"]:
            return tier

    # Should not reach here if tiers include a catch-all (max_vix: 999)
    return tiers[-1]


def _compute_skew(bull_share: float, neutral_zone: list, max_skew_ratio: float) -> float:
    """Compute skew adjustment factor from bull_share.

    Returns a value in [-max_skew_ratio, +max_skew_ratio].
    Positive = bullish (tighten call, loosen put).
    Negative = bearish (tighten put, loosen call).
    Zero = neutral (no skew).

    Skew clamps to max at bull_share <= 0.30 or >= 0.70 (strongly directional).
    Between neutral zone and clamp point, scales linearly.
    """
    low, high = neutral_zone
    # Clamp points where max skew is reached
    clamp_low = 0.30
    clamp_high = 0.70

    if low <= bull_share <= high:
        return 0.0

    if bull_share < low:
        # Bearish: scale linearly from 0 at low to -max_skew_ratio at clamp_low
        if bull_share <= clamp_low:
            return -max_skew_ratio
        distance = (low - bull_share) / (low - clamp_low) if low > clamp_low else 1.0
        return -min(distance, 1.0) * max_skew_ratio
    else:
        # Bullish: scale linearly from 0 at high to +max_skew_ratio at clamp_high
        if bull_share >= clamp_high:
            return max_skew_ratio
        distance = (bull_share - high) / (clamp_high - high) if clamp_high > high else 1.0
        return min(distance, 1.0) * max_skew_ratio


def compute_adaptive_params(
    bull_share: float,
    vix: float | None,
    base_config: dict,
    adaptive_config: dict,
) -> dict:
    """Compute VIX-scaled, direction-skewed parameters.

    Args:
        bull_share: Directional signal (0.0 = strongly bearish, 1.0 = strongly bullish)
        vix: Current VIX level (None if unavailable)
        base_config: User's strategy.yaml selection section
        adaptive_config: User's strategy.yaml adaptive section

    Returns:
        Dict with put/call delta ranges and DTE range.
    """
    tiers = adaptive_config.get("vix_tiers", [_FALLBACK_TIER])
    skew_cfg = adaptive_config.get("skew", {})
    neutral_zone = skew_cfg.get("neutral_zone", [0.45, 0.55])
    max_skew_ratio = skew_cfg.get("max_skew_ratio", 0.25)

    # Step 1: VIX tier -> delta scale + DTE range
    tier = _get_vix_tier(vix, tiers)
    delta_scale = tier["delta_scale"]
    dte_min = tier["dte_min"]
    dte_max = tier["dte_max"]
    dte_ideal = (dte_min + dte_max) // 2

    # Step 2: Directional skew
    skew = _compute_skew(bull_share, neutral_zone, max_skew_ratio)

    # Step 3: Apply VIX scale and skew to both min and max independently
    # Negative skew (bearish): put delta shrinks via (1 + negative), call delta grows via (1 - negative)
    put_delta_min = base_config.get("put_delta_min", 0.08) * delta_scale * (1 + skew)
    put_delta_max = base_config.get("put_delta_max", 0.15) * delta_scale * (1 + skew)
    call_delta_min = base_config.get("call_delta_min", 0.08) * delta_scale * (1 - skew)
    call_delta_max = base_config.get("call_delta_max", 0.15) * delta_scale * (1 - skew)

    return {
        "put_delta_min": put_delta_min,
        "put_delta_max": put_delta_max,
        "call_delta_min": call_delta_min,
        "call_delta_max": call_delta_max,
        "dte_min": dte_min,
        "dte_max": dte_max,
        "dte_ideal": dte_ideal,
    }
