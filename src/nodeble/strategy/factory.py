# -*- coding: utf-8 -*-
"""Iron condor factory: IV-based systematic condor scanning.

No signal dependency — purely IV rank driven. Always sells iron condors
(both sides required, no single-side fallback).
"""

import logging
from datetime import date

import yaml

from nodeble.core.state import SpreadState
from nodeble.core import risk as options_risk
from nodeble.strategy.strike_selector import (
    get_spread_width,
    select_put_spread_strikes,
    select_call_spread_strikes,
    build_candidate,
    SpreadCandidate,
)
from nodeble.strategy.chain_screener import (
    screen_symbol_iv,
    is_earnings_blackout,
    select_best_expiry,
    fetch_chain_and_price,
)
from nodeble.data.chain_recorder import record_chain_snapshot

logger = logging.getLogger(__name__)

DEFAULT_STRATEGY_PATH = "config_condor/strategy.yaml"


def load_strategy_config(path: str = DEFAULT_STRATEGY_PATH) -> dict:
    """Load condor strategy config."""
    with open(path, "r") as f:
        cfg = yaml.safe_load(f) or {}
    return cfg


def _build_condor_config(strategy_cfg: dict) -> dict:
    """Build a config dict compatible with strike_selector functions.

    The condor uses separate put/call delta ranges (farther OTM than
    directional spreads), so we adapt them for each side.
    """
    sel = strategy_cfg.get("selection", {})
    return {
        "selection": {
            "delta_range": [sel.get("put_delta_min", 0.10), sel.get("put_delta_max", 0.20)],
            "min_open_interest": sel.get("min_open_interest", 100),
            "max_spread_pct": sel.get("max_spread_pct", 0.10),
            "min_credit_pct": sel.get("min_credit_pct", 0.25),
            "max_risk_per_trade": strategy_cfg.get("management", {}).get("max_risk_per_trade", 500),
        },
        "sizing": strategy_cfg.get("sizing", {}),
    }


def _build_call_config(strategy_cfg: dict) -> dict:
    """Like _build_condor_config but uses call delta range."""
    sel = strategy_cfg.get("selection", {})
    return {
        "selection": {
            "delta_range": [sel.get("call_delta_min", 0.10), sel.get("call_delta_max", 0.20)],
            "min_open_interest": sel.get("min_open_interest", 100),
            "max_spread_pct": sel.get("max_spread_pct", 0.10),
            "min_credit_pct": sel.get("min_credit_pct", 0.25),
            "max_risk_per_trade": strategy_cfg.get("management", {}).get("max_risk_per_trade", 500),
        },
        "sizing": strategy_cfg.get("sizing", {}),
    }


def scan_for_condors(
    broker,
    state: SpreadState,
    risk_cfg: dict,
    strategy_cfg: dict,
    dry_run: bool = False,
) -> tuple[list[SpreadCandidate], list[dict]]:
    """Main iron condor scanning algorithm.

    1. Iterate watchlist from config
    2. Batch IV rank screening — skip if below threshold
    3. Per symbol: earnings blackout (fail-closed), symbol limit
    4. Select best expiry (DTE 21-45, prefer monthly)
    5. Fetch put chain → select put spread strikes
    6. Fetch call chain → select call spread strikes
    7. Both sides MUST qualify → build iron condor candidate
       NO single-side fallback (that's a directional bet)
    8. Sort by credit/risk ratio

    Returns (candidates sorted by credit/risk ratio, rejections list).
    Does NOT place orders — caller decides.
    """
    sel = strategy_cfg.get("selection", {})
    watchlist = strategy_cfg.get("watchlist", [])

    rejections: list[dict] = []

    if not watchlist:
        logger.warning("Empty watchlist — nothing to scan")
        return [], rejections

    # VIX scaling — apply tier overrides to selection config
    from nodeble.data.vix import get_vix, apply_vix_overrides
    vix_scaling = strategy_cfg.get("vix_scaling", {})
    if vix_scaling.get("enabled", False):
        vix = get_vix()
        sel = apply_vix_overrides(sel, vix, vix_scaling)

    # 1. Batch IV rank screening
    min_iv_rank = sel.get("min_iv_rank", 0.35)
    iv_map, iv_analyses = screen_symbol_iv(broker, watchlist)

    min_iv_rv_ratio = sel.get("min_iv_rv_ratio", 0)

    # Filter by IV rank
    iv_qualified = {}
    for sym in watchlist:
        iv_rank = iv_map.get(sym)
        if iv_rank is None:
            rejections.append({
                "symbol": sym, "spread_type": "iron_condor",
                "reason": "no IV rank data",
            })
            continue
        if iv_rank < min_iv_rank:
            rejections.append({
                "symbol": sym, "spread_type": "iron_condor",
                "reason": f"IV rank {iv_rank:.2f} < min {min_iv_rank}",
            })
            continue
        iv_qualified[sym] = iv_rank

    if not iv_qualified:
        logger.info("No symbols passed IV rank screening — nothing to scan")
        return [], rejections

    # IV/RV ratio computation (batch)
    iv_rv_map: dict[str, dict] = {}
    try:
        from nodeble.strategy.chain_screener import compute_iv_rv_ratios
        iv_rv_map = compute_iv_rv_ratios(iv_analyses, list(iv_qualified.keys()))
    except Exception as e:
        logger.warning(f"IV/RV computation failed (continuing without filter): {e}")

    # Filter by IV/RV ratio
    if min_iv_rv_ratio > 0 and iv_rv_map:
        filtered = {}
        for sym, iv_rank in iv_qualified.items():
            iv_rv_data = iv_rv_map.get(sym)
            if iv_rv_data:
                logger.info(f"{sym}: IV/RV ratio {iv_rv_data['ratio']:.2f} (IV={iv_rv_data['iv']:.1%}, RV={iv_rv_data['rv']:.1%})")
                if iv_rv_data["ratio"] < min_iv_rv_ratio:
                    rejections.append({
                        "symbol": sym, "spread_type": "iron_condor",
                        "reason": f"IV/RV ratio {iv_rv_data['ratio']:.2f} < min {min_iv_rv_ratio}",
                    })
                    continue
            filtered[sym] = iv_rank
        iv_qualified = filtered
    else:
        # Log ratios even when filter disabled
        for sym in iv_qualified:
            iv_rv_data = iv_rv_map.get(sym)
            if iv_rv_data:
                logger.info(f"{sym}: IV/RV ratio {iv_rv_data['ratio']:.2f} (IV={iv_rv_data['iv']:.1%}, RV={iv_rv_data['rv']:.1%})")

    today = date.today()
    all_candidates = []
    blackout_days = sel.get("earnings_blackout_days", 7)
    max_per_run = sel.get("max_new_positions_per_run", 0)

    for symbol, iv_rank in iv_qualified.items():
        # 2. Per-symbol limit
        if not options_risk.check_symbol_limit(symbol, state, risk_cfg):
            reason = f"symbol limit reached ({symbol} already at max)"
            logger.info(f"{symbol}: {reason}")
            rejections.append({"symbol": symbol, "spread_type": "iron_condor", "reason": reason})
            continue

        # Cooldown timer
        cooldown_days = sel.get("cooldown_days", 0)
        if cooldown_days > 0:
            from nodeble.strategy.chain_screener import check_cooldown
            cd_ok, cd_reason = check_cooldown(symbol, state.positions, cooldown_days, ref_date=today)
            if not cd_ok:
                logger.info(f"{symbol}: cooldown — {cd_reason}")
                rejections.append({"symbol": symbol, "spread_type": "iron_condor", "reason": f"cooldown: {cd_reason}"})
                continue

        # 3. Earnings blackout (fail-closed)
        if is_earnings_blackout(symbol, blackout_days=blackout_days):
            rejections.append({"symbol": symbol, "spread_type": "iron_condor", "reason": "earnings blackout"})
            continue

        # 4. Get expirations and select best
        try:
            expirations = broker.get_option_expirations(symbol)
        except Exception as e:
            reason = f"expirations fetch failed: {e}"
            logger.warning(f"{symbol}: {reason}")
            rejections.append({"symbol": symbol, "spread_type": "iron_condor", "reason": reason})
            continue

        best_expiry = select_best_expiry(
            expirations,
            dte_min=sel.get("dte_min", 21),
            dte_max=sel.get("dte_max", 45),
            dte_ideal=sel.get("dte_ideal", 30),
            prefer_monthly=sel.get("prefer_monthly", True),
            ref_date=today,
        )
        if not best_expiry:
            reason = f"no valid expiry in DTE range [{sel.get('dte_min', 21)}-{sel.get('dte_max', 45)}]"
            logger.info(f"{symbol}: {reason}")
            rejections.append({"symbol": symbol, "spread_type": "iron_condor", "reason": reason})
            continue

        dte = (date.fromisoformat(best_expiry) - today).days

        # 5. Get stock price for spread width (3-tier fallback)
        stock_price = broker.get_stock_price(symbol)

        if stock_price <= 0:
            reason = "no stock price available"
            logger.warning(f"{symbol}: {reason} — skipping")
            rejections.append({"symbol": symbol, "spread_type": "iron_condor", "reason": reason})
            continue

        width = get_spread_width(stock_price, strategy_cfg)

        # 6. Fetch put chain + select put spread strikes
        put_config = _build_condor_config(strategy_cfg)
        put_side = None
        try:
            put_filter = {
                "delta_min": -0.50,
                "delta_max": 0.0,
                "open_interest_min": sel.get("min_open_interest", 100) // 2,
                "in_the_money": False,
            }
            put_chain = broker.get_option_chain(
                symbol=symbol, expiry=best_expiry, option_filter=put_filter,
            )
            record_chain_snapshot(symbol, best_expiry, put_chain, stock_price=stock_price, iv_rank=iv_rank, iv_rv_ratio=iv_rv_map.get(symbol, {}).get("ratio", 0.0), source="condor")
            put_side = select_put_spread_strikes(put_chain, stock_price, width, put_config)
        except Exception as e:
            logger.warning(f"{symbol}: failed to get put chain: {e}")

        # 7. Fetch call chain + select call spread strikes
        call_config = _build_call_config(strategy_cfg)
        call_side = None
        try:
            call_filter = {
                "delta_min": 0.0,
                "delta_max": 0.50,
                "open_interest_min": sel.get("min_open_interest", 100) // 2,
                "in_the_money": False,
            }
            call_chain = broker.get_option_chain(
                symbol=symbol, expiry=best_expiry, option_filter=call_filter,
            )
            record_chain_snapshot(symbol, best_expiry, call_chain, stock_price=stock_price, iv_rank=iv_rank, iv_rv_ratio=iv_rv_map.get(symbol, {}).get("ratio", 0.0), source="condor")
            call_side = select_call_spread_strikes(call_chain, stock_price, width, call_config)
        except Exception as e:
            logger.warning(f"{symbol}: failed to get call chain: {e}")

        # 8. BOTH sides must qualify — no single-side fallback
        if put_side is None or call_side is None:
            missing = []
            if put_side is None:
                missing.append("put")
            if call_side is None:
                missing.append("call")
            reason = f"iron condor requires both sides ({', '.join(missing)} side failed, exp={best_expiry}, width=${width:.0f})"
            logger.info(f"{symbol}: {reason}")
            rejections.append({
                "symbol": symbol, "spread_type": "iron_condor",
                "expiry": best_expiry, "reason": reason,
            })
            continue

        # Build candidate using put_config for credit check (both configs share min_credit_pct)
        candidate = build_candidate(
            underlying=symbol,
            spread_type="iron_condor",
            expiry=best_expiry,
            dte=dte,
            put_side=put_side,
            call_side=call_side,
            width=width,
            config=put_config,
            iv_rank=iv_rank,
        )

        if candidate:
            candidate.scan_price = stock_price
            candidate.iv_rv_ratio = iv_rv_map.get(symbol, {}).get("ratio", 0.0)
            all_candidates.append(candidate)
            if max_per_run > 0 and len(all_candidates) >= max_per_run:
                logger.info(f"Per-run limit reached ({max_per_run} condor candidates) — stopping scan")
                break
        else:
            min_credit_pct = sel.get("min_credit_pct", 0.25)
            reason = f"credit below min ({min_credit_pct:.0%} of ${width:.0f} = ${min_credit_pct * width:.2f})"
            logger.info(f"{symbol}: {reason} (exp={best_expiry})")
            rejections.append({
                "symbol": symbol, "spread_type": "iron_condor",
                "expiry": best_expiry, "reason": reason,
            })

    # Sort by credit/risk ratio (best first)
    all_candidates.sort(key=lambda c: c.credit_risk_ratio, reverse=True)
    logger.info(
        f"Condor scan found {len(all_candidates)} candidates, "
        f"{len(rejections)} rejections across {len(watchlist)} symbols"
    )
    return all_candidates, rejections
