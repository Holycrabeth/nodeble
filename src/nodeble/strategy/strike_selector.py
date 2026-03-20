# -*- coding: utf-8 -*-
"""Strike selection and spread width logic for credit spreads."""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SpreadCandidate:
    """A candidate spread opportunity."""

    underlying: str
    spread_type: str  # bull_put / bear_call / iron_condor
    expiry: str
    dte: int

    # Put side (bull_put or put side of iron condor)
    short_put_identifier: str = ""
    short_put_strike: float = 0.0
    short_put_delta: float = 0.0
    short_put_bid: float = 0.0
    long_put_identifier: str = ""
    long_put_strike: float = 0.0
    long_put_delta: float = 0.0
    long_put_ask: float = 0.0
    put_credit: float = 0.0  # short_put_bid - long_put_ask (per share)

    # Call side (bear_call or call side of iron condor)
    short_call_identifier: str = ""
    short_call_strike: float = 0.0
    short_call_delta: float = 0.0
    short_call_bid: float = 0.0
    long_call_identifier: str = ""
    long_call_strike: float = 0.0
    long_call_delta: float = 0.0
    long_call_ask: float = 0.0
    call_credit: float = 0.0

    scan_price: float = 0.0  # underlying price at scan time (for price guard)

    spread_width: float = 0.0
    total_credit: float = 0.0  # per share
    max_risk: float = 0.0  # per share (width - credit)
    credit_risk_ratio: float = 0.0  # credit / max_risk
    iv_rank: float = 0.0
    iv_rv_ratio: float = 0.0
    contracts: int = 1


def get_spread_width(stock_price: float, config: dict) -> float:
    """Determine spread width based on stock price.

    Uses rules from config: [{max_price: 200, width: 5}, ...]
    """
    rules = config.get("sizing", {}).get("spread_width_rules", [
        {"max_price": 200, "width": 5},
        {"max_price": 500, "width": 10},
        {"max_price": 999999, "width": 15},
    ])
    for rule in sorted(rules, key=lambda r: r["max_price"]):
        if stock_price <= rule["max_price"]:
            return float(rule["width"])
    return 15.0


def _get(item, key, alt_key=None, default=0):
    """Get a value from a dict or object."""
    if isinstance(item, dict):
        val = item.get(key, item.get(alt_key, default) if alt_key else default)
    else:
        val = getattr(item, key, getattr(item, alt_key, default) if alt_key else default)
    return val


def _find_closest_strike(chain: list, target_strike: float, put_call: str) -> dict | None:
    """Find the option closest to target_strike with matching put_call."""
    best = None
    best_dist = float("inf")
    for item in chain:
        pc = str(_get(item, "put_call", "right", "")).upper()
        if pc not in ("PUT", "P") and put_call == "P":
            continue
        if pc not in ("CALL", "C") and put_call == "C":
            continue
        strike = float(_get(item, "strike", default=0) or 0)
        dist = abs(strike - target_strike)
        if dist < best_dist:
            best_dist = dist
            best = item
    return best


def select_put_spread_strikes(
    chain: list,
    stock_price: float,
    width: float,
    config: dict,
) -> tuple[dict, dict] | None:
    """Select short put and long put strikes for a bull put spread.

    Short put: delta in [-0.30, -0.15] (OTM), highest bid in range.
    Long put: strike = short_strike - width (closest available).

    Returns (short_put, long_put) dicts or None.
    """
    sel = config.get("selection", {})
    delta_range = sel.get("delta_range", [0.15, 0.30])
    min_oi = sel.get("min_open_interest", 100)
    max_spread_pct = sel.get("max_spread_pct", 0.20)

    # Filter to qualifying short puts
    short_candidates = []
    for item in chain:
        pc = str(_get(item, "put_call", "right", "")).upper()
        if pc not in ("PUT", "P"):
            continue
        delta = float(_get(item, "delta", default=0) or 0)
        bid = float(_get(item, "bid_price", default=0) or 0)
        ask = float(_get(item, "ask_price", default=0) or 0)
        oi = int(float(_get(item, "open_interest", default=0) or 0))
        strike = float(_get(item, "strike", default=0) or 0)

        # Delta filter (put deltas are negative)
        abs_delta = abs(delta)
        if abs_delta < delta_range[0] or abs_delta > delta_range[1]:
            continue
        if oi < min_oi:
            continue
        if bid <= 0:
            continue
        mid = (bid + ask) / 2 if ask > 0 else bid
        if mid > 0 and ask > 0:
            spread = (ask - bid) / mid
            if spread > max_spread_pct:
                continue

        short_candidates.append({
            "identifier": str(_get(item, "identifier", default="")),
            "strike": strike,
            "delta": delta,
            "bid": bid,
            "ask": ask,
            "open_interest": oi,
        })

    if not short_candidates:
        return None

    # Pick highest bid (best premium)
    short_candidates.sort(key=lambda c: c["bid"], reverse=True)
    short_put = short_candidates[0]

    # Find long put at short_strike - width
    target_long = short_put["strike"] - width
    long_put_item = _find_closest_strike(chain, target_long, "P")
    if long_put_item is None:
        return None

    long_put = {
        "identifier": str(_get(long_put_item, "identifier", default="")),
        "strike": float(_get(long_put_item, "strike", default=0) or 0),
        "ask": float(_get(long_put_item, "ask_price", default=0) or 0),
        "bid": float(_get(long_put_item, "bid_price", default=0) or 0),
        "delta": float(_get(long_put_item, "delta", default=0) or 0),
    }

    if long_put["ask"] <= 0:
        return None

    return short_put, long_put


def select_call_spread_strikes(
    chain: list,
    stock_price: float,
    width: float,
    config: dict,
) -> tuple[dict, dict] | None:
    """Select short call and long call strikes for a bear call spread.

    Short call: delta in [0.15, 0.30] (OTM), highest bid in range.
    Long call: strike = short_strike + width (closest available).

    Returns (short_call, long_call) dicts or None.
    """
    sel = config.get("selection", {})
    delta_range = sel.get("delta_range", [0.15, 0.30])
    min_oi = sel.get("min_open_interest", 100)
    max_spread_pct = sel.get("max_spread_pct", 0.20)

    short_candidates = []
    for item in chain:
        pc = str(_get(item, "put_call", "right", "")).upper()
        if pc not in ("CALL", "C"):
            continue
        delta = float(_get(item, "delta", default=0) or 0)
        bid = float(_get(item, "bid_price", default=0) or 0)
        ask = float(_get(item, "ask_price", default=0) or 0)
        oi = int(float(_get(item, "open_interest", default=0) or 0))
        strike = float(_get(item, "strike", default=0) or 0)

        # Delta filter (call deltas are positive)
        if delta < delta_range[0] or delta > delta_range[1]:
            continue
        if oi < min_oi:
            continue
        if bid <= 0:
            continue
        mid = (bid + ask) / 2 if ask > 0 else bid
        if mid > 0 and ask > 0:
            spread = (ask - bid) / mid
            if spread > max_spread_pct:
                continue

        short_candidates.append({
            "identifier": str(_get(item, "identifier", default="")),
            "strike": strike,
            "delta": delta,
            "bid": bid,
            "ask": ask,
            "open_interest": oi,
        })

    if not short_candidates:
        return None

    short_candidates.sort(key=lambda c: c["bid"], reverse=True)
    short_call = short_candidates[0]

    target_long = short_call["strike"] + width
    long_call_item = _find_closest_strike(chain, target_long, "C")
    if long_call_item is None:
        return None

    long_call = {
        "identifier": str(_get(long_call_item, "identifier", default="")),
        "strike": float(_get(long_call_item, "strike", default=0) or 0),
        "ask": float(_get(long_call_item, "ask_price", default=0) or 0),
        "bid": float(_get(long_call_item, "bid_price", default=0) or 0),
        "delta": float(_get(long_call_item, "delta", default=0) or 0),
    }

    if long_call["ask"] <= 0:
        return None

    return short_call, long_call


def build_candidate(
    underlying: str,
    spread_type: str,
    expiry: str,
    dte: int,
    put_side: tuple[dict, dict] | None,
    call_side: tuple[dict, dict] | None,
    width: float,
    config: dict,
    iv_rank: float = 0.0,
) -> SpreadCandidate | None:
    """Build a SpreadCandidate from selected strikes.

    Validates minimum credit requirement.
    """
    sel = config.get("selection", {})
    min_credit_pct = sel.get("min_credit_pct", 0.30)
    max_risk_per_trade = sel.get("max_risk_per_trade", 500)

    candidate = SpreadCandidate(
        underlying=underlying,
        spread_type=spread_type,
        expiry=expiry,
        dte=dte,
        spread_width=width,
        iv_rank=iv_rank,
    )

    total_credit = 0.0

    if put_side and spread_type in ("bull_put", "iron_condor"):
        short_put, long_put = put_side
        put_credit = short_put["bid"] - long_put["ask"]
        if put_credit <= 0:
            if spread_type == "bull_put":
                return None
            # For iron condor, call side might still work
        else:
            candidate.short_put_identifier = short_put["identifier"]
            candidate.short_put_strike = short_put["strike"]
            candidate.short_put_delta = short_put.get("delta", 0)
            candidate.short_put_bid = short_put["bid"]
            candidate.long_put_identifier = long_put["identifier"]
            candidate.long_put_strike = long_put["strike"]
            candidate.long_put_delta = long_put.get("delta", 0)
            candidate.long_put_ask = long_put["ask"]
            candidate.put_credit = put_credit
            total_credit += put_credit

    if call_side and spread_type in ("bear_call", "iron_condor"):
        short_call, long_call = call_side
        call_credit = short_call["bid"] - long_call["ask"]
        if call_credit <= 0:
            if spread_type == "bear_call":
                return None
        else:
            candidate.short_call_identifier = short_call["identifier"]
            candidate.short_call_strike = short_call["strike"]
            candidate.short_call_delta = short_call.get("delta", 0)
            candidate.short_call_bid = short_call["bid"]
            candidate.long_call_identifier = long_call["identifier"]
            candidate.long_call_strike = long_call["strike"]
            candidate.long_call_delta = long_call.get("delta", 0)
            candidate.long_call_ask = long_call["ask"]
            candidate.call_credit = call_credit
            total_credit += call_credit

    if total_credit <= 0:
        return None

    candidate.total_credit = total_credit

    # For iron condor, max_risk = max(put_width, call_width) - total_credit
    # because only one side can be at max loss at a time
    if spread_type == "iron_condor" and put_side and call_side:
        put_width = abs(put_side[0]["strike"] - put_side[1]["strike"])
        call_width = abs(call_side[0]["strike"] - call_side[1]["strike"])
        effective_width = max(put_width, call_width)
        candidate.max_risk = effective_width - total_credit
    else:
        candidate.max_risk = width - total_credit

    if candidate.max_risk <= 0:
        candidate.max_risk = 0.01  # avoid div by zero

    candidate.credit_risk_ratio = total_credit / candidate.max_risk

    # Validate minimum credit
    if total_credit < min_credit_pct * width:
        logger.debug(
            f"{underlying}: credit ${total_credit:.2f} < "
            f"{min_credit_pct:.0%} of ${width:.0f} width — skip"
        )
        return None

    # Compute contracts based on max_risk_per_trade
    max_risk_per_spread = candidate.max_risk * 100  # per contract
    if max_risk_per_spread > 0:
        candidate.contracts = max(1, int(max_risk_per_trade / max_risk_per_spread))
    else:
        candidate.contracts = 1

    return candidate
