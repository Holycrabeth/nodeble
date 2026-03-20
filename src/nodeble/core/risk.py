# -*- coding: utf-8 -*-
"""Options spread risk checks: cash floor, spread limits, exposure cap, naked leg verification."""

import logging
from pathlib import Path

import yaml

from nodeble.core.state import SpreadState, SpreadPosition

logger = logging.getLogger(__name__)


def load_risk_config(path: str) -> dict:
    """Load options risk config with fallback defaults.

    Returns a FLAT dict (no 'risk' wrapper) — the functions in this module
    expect top-level keys like 'kill_switch', 'min_cash_floor', etc.
    """
    defaults = {
        "kill_switch": False,
        "min_cash_floor": 20000,
        "max_concurrent_spreads": 10,
        "max_spreads_per_symbol": 2,
        "max_daily_orders": 20,
        "max_daily_loss": 1500,
        "max_total_exposure": 5000,
        "max_portfolio_delta": 200,
    }
    try:
        with open(path, "r") as f:
            raw = yaml.safe_load(f) or {}
        defaults["_version"] = raw.get("version", "unknown")
        risk = raw.get("risk", {})
        for key in list(defaults.keys()):
            if key in risk:
                defaults[key] = risk[key]
    except FileNotFoundError:
        defaults["_version"] = "fallback"
        logger.warning(f"Options risk config not found: {path}, using defaults")
    return defaults


def check_kill_switch(risk_cfg: dict) -> bool:
    """Returns True if trading is allowed (kill switch OFF)."""
    if risk_cfg.get("kill_switch"):
        logger.warning("OPTIONS KILL SWITCH is ON — blocking all operations")
        return False
    return True


def check_cash_floor(broker, risk_cfg: dict) -> tuple[bool, float]:
    """Check if cash_available_for_trade exceeds minimum floor.

    Returns (has_budget, cash_available).
    Fail-closed: returns (False, 0.0) on API error.
    """
    floor = risk_cfg.get("min_cash_floor", 20000)
    try:
        assets = broker.get_assets()
        seg = assets.segments.get("S") if hasattr(assets, "segments") else None
        if not seg:
            logger.error("No account segment found — fail-closed, returning 0")
            return False, 0.0
        cash = float(
            getattr(seg, "cash_available_for_trade", None)
            or seg.cash_balance
            or 0
        )
        logger.info(f"Cash available for trade: ${cash:,.0f}")
    except Exception as e:
        logger.error(f"Failed to get account cash — fail-closed: {e}")
        return False, 0.0

    if cash < floor:
        logger.info(f"Cash ${cash:,.0f} below floor ${floor:,.0f} — no new orders")
        return False, cash
    return True, cash


def check_max_spreads(state: SpreadState, risk_cfg: dict) -> bool:
    """Check if under max concurrent spread limit."""
    current = state.get_active_count()
    limit = risk_cfg.get("max_concurrent_spreads", 10)
    if current >= limit:
        logger.info(f"Max spreads reached: {current} >= {limit}")
        return False
    return True


def check_symbol_limit(symbol: str, state: SpreadState, risk_cfg: dict) -> bool:
    """Check per-symbol spread limit."""
    current = state.get_symbol_count(symbol)
    limit = risk_cfg.get("max_spreads_per_symbol", 2)
    if current >= limit:
        logger.info(f"Max spreads for {symbol}: {current} >= {limit}")
        return False
    return True


def check_daily_loss(state: SpreadState, risk_cfg: dict) -> bool:
    """Check if daily realized loss exceeds limit.

    Returns True if trading is allowed.
    """
    from datetime import date
    today_str = date.today().isoformat()
    daily_pnl = state.get_daily_pnl(today_str)
    limit = risk_cfg.get("max_daily_loss", 1500)
    if daily_pnl < -limit:
        logger.warning(f"Daily loss ${daily_pnl:,.0f} exceeds limit -${limit:,.0f}")
        return False
    return True


def check_total_exposure(state: SpreadState, risk_cfg: dict, additional: float = 0) -> bool:
    """Check if total exposure (max_risk * contracts * 100) is within limit.

    Args:
        additional: additional exposure from a new spread being considered.
    """
    current = state.get_total_exposure()
    total = current + additional
    limit = risk_cfg.get("max_total_exposure", 5000)
    if total > limit:
        logger.info(f"Total exposure ${total:,.0f} would exceed limit ${limit:,.0f}")
        return False
    return True


def check_portfolio_delta(state: SpreadState, risk_cfg: dict, additional: float = 0) -> bool:
    """Check if portfolio delta is within limit (absolute value)."""
    current = state.get_total_delta()
    total = current + additional
    limit = risk_cfg.get("max_portfolio_delta", 200)
    if abs(total) > limit:
        logger.info(f"Portfolio delta {total:.0f} would exceed limit +/-{limit}")
        return False
    return True


def verify_no_naked_legs(position: SpreadPosition) -> bool:
    """CRITICAL: Verify every SELL leg has a covering BUY leg.

    A SELL leg is covered if there exists a BUY leg with:
    - Same put_call (P or C)
    - Contracts >= SELL leg contracts
    - Status is filled or pending

    Returns True if no naked legs found (safe).
    Returns False if any SELL leg is uncovered (DANGEROUS).
    """
    active_statuses = ("filled", "pending")

    buy_legs: dict[str, int] = {}
    sell_legs: dict[str, int] = {}

    for leg in position.legs:
        if leg.status not in active_statuses:
            continue
        if leg.action == "BUY":
            buy_legs[leg.put_call] = buy_legs.get(leg.put_call, 0) + leg.contracts
        elif leg.action == "SELL":
            sell_legs[leg.put_call] = sell_legs.get(leg.put_call, 0) + leg.contracts

    for pc, sell_qty in sell_legs.items():
        buy_qty = buy_legs.get(pc, 0)
        if buy_qty < sell_qty:
            logger.error(
                f"NAKED LEG DETECTED: {position.spread_id} — "
                f"SELL {sell_qty} {pc} but only BUY {buy_qty} {pc} covering"
            )
            return False

    return True
