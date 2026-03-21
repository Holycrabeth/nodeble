# -*- coding: utf-8 -*-
"""Day-by-day iron condor simulation engine."""
import logging
from dataclasses import dataclass, field
from datetime import timedelta

import numpy as np
import pandas as pd

from nodeble.backtest.pricing import bs_price, bs_delta, find_strike_for_delta, RISK_FREE_RATE

logger = logging.getLogger(__name__)

WARMUP_DAYS = 252


@dataclass
class BacktestParams:
    put_delta: float = 0.15
    call_delta: float = 0.15
    dte: int = 30
    spread_width: float = 10.0
    profit_target_pct: float = 0.50
    stop_loss_pct: float = 2.0
    close_before_dte: int = 3
    cooldown_days: int = 5
    use_adaptive: bool = True
    use_indicators: bool = True


@dataclass
class BacktestPosition:
    symbol: str
    entry_date: object  # date
    expiry_date: object  # date
    entry_dte: int
    short_put_strike: float
    long_put_strike: float
    short_call_strike: float
    long_call_strike: float
    entry_credit: float
    entry_vix: float
    entry_vix9d: float | None = None
    entry_term_ratio: float | None = None
    entry_bull_share: float = 0.50
    entry_indicator_votes: dict = field(default_factory=dict)


@dataclass
class TradeResult:
    position: BacktestPosition
    exit_date: object  # date
    exit_value: float
    pnl: float
    pnl_pct: float
    exit_reason: str
    max_adverse_excursion: float
    days_held: int


def _price_ic(S: float, pos: BacktestPosition, dte_remaining: int, sigma: float) -> float:
    """Price the IC (cost to close) using Black-Scholes."""
    T = max(dte_remaining, 0) / 365.0
    if T <= 0:
        sp = max(pos.short_put_strike - S, 0.0)
        lp = max(pos.long_put_strike - S, 0.0)
        sc = max(S - pos.short_call_strike, 0.0)
        lc = max(S - pos.long_call_strike, 0.0)
        return (sp - lp) + (sc - lc)

    r = RISK_FREE_RATE
    sp = bs_price(S, pos.short_put_strike, T, r, sigma, "put")
    lp = bs_price(S, pos.long_put_strike, T, r, sigma, "put")
    sc = bs_price(S, pos.short_call_strike, T, r, sigma, "call")
    lc = bs_price(S, pos.long_call_strike, T, r, sigma, "call")
    return (sp - lp) + (sc - lc)


def simulate_ic(
    symbol: str,
    ohlcv: pd.DataFrame,
    vix: pd.Series,
    vix9d: pd.Series,
    params: BacktestParams,
    adaptive_config: dict | None = None,
) -> list[TradeResult]:
    """Run day-by-day IC simulation on historical data."""
    results: list[TradeResult] = []
    position: BacktestPosition | None = None
    last_close_idx = -params.cooldown_days - 1
    max_adverse = 0.0

    dates = ohlcv.index
    if len(dates) < WARMUP_DAYS + 30:
        logger.warning(f"{symbol}: Not enough data ({len(dates)} days, need {WARMUP_DAYS + 30})")
        return results

    # Pre-compute indicators if needed
    indicator_cache = {}
    if params.use_indicators:
        try:
            from nodeble.signals.registry import get_all_indicators
            from nodeble.signals.scorer import VotingEngine
            indicators = get_all_indicators()
            engine = VotingEngine()
            for i in range(WARMUP_DAYS, len(dates)):
                window = ohlcv.iloc[max(0, i - WARMUP_DAYS):i + 1]
                result = engine.score(symbol, window, indicators)
                indicator_cache[dates[i]] = {
                    "bull_share": result.bull_share,
                    "votes": result.votes,
                }
        except Exception as e:
            logger.warning(f"Indicator computation failed: {e}. Running without indicators.")
            params.use_indicators = False

    for i in range(WARMUP_DAYS, len(dates)):
        today = dates[i]
        today_date = today.date() if hasattr(today, "date") else today
        price = float(ohlcv.iloc[i]["close"])

        # Get VIX for today
        current_vix = float(vix.get(today, 20.0)) if today in vix.index else 20.0
        current_vix9d = float(vix9d.get(today, 0.0)) if today in vix9d.index else None
        if current_vix9d == 0.0:
            current_vix9d = None
        sigma = current_vix / 100.0

        # Compute term ratio
        term_ratio = None
        if current_vix9d is not None and current_vix > 0:
            term_ratio = current_vix9d / current_vix

        # Get indicator signal
        bull_share = 0.50
        indicator_votes = {}
        if params.use_indicators and today in indicator_cache:
            bull_share = indicator_cache[today]["bull_share"]
            indicator_votes = indicator_cache[today]["votes"]

        # Determine deltas and DTE
        put_delta = params.put_delta
        call_delta = params.call_delta
        target_dte = params.dte

        if params.use_adaptive and adaptive_config:
            try:
                from nodeble.strategy.adaptive import compute_adaptive_params
                sel = {
                    "put_delta_min": params.put_delta * 0.5,
                    "put_delta_max": params.put_delta,
                    "call_delta_min": params.call_delta * 0.5,
                    "call_delta_max": params.call_delta,
                }
                adjusted = compute_adaptive_params(
                    bull_share, current_vix, sel, adaptive_config, term_ratio=term_ratio,
                )
                put_delta = (adjusted["put_delta_min"] + adjusted["put_delta_max"]) / 2
                call_delta = (adjusted["call_delta_min"] + adjusted["call_delta_max"]) / 2
                target_dte = adjusted["dte_ideal"]
            except Exception as e:
                logger.debug(f"Adaptive failed on {today}: {e}")

        # --- Position Management ---
        if position is not None:
            dte_remaining = (position.expiry_date - today_date).days
            current_value = _price_ic(price, position, dte_remaining, sigma)

            unrealized_pnl = position.entry_credit - current_value
            if unrealized_pnl < max_adverse:
                max_adverse = unrealized_pnl

            exit_reason = None
            if dte_remaining <= 0:
                exit_reason = "expiration"
            elif current_value <= position.entry_credit * params.profit_target_pct:
                exit_reason = "profit_target"
            elif current_value >= position.entry_credit * params.stop_loss_pct:
                exit_reason = "stop_loss"
            elif dte_remaining <= params.close_before_dte:
                exit_reason = "dte_close"

            if exit_reason:
                pnl = position.entry_credit - current_value
                max_risk = params.spread_width
                results.append(TradeResult(
                    position=position,
                    exit_date=today_date,
                    exit_value=current_value,
                    pnl=pnl,
                    pnl_pct=pnl / max_risk if max_risk > 0 else 0.0,
                    exit_reason=exit_reason,
                    max_adverse_excursion=max_adverse,
                    days_held=(today_date - position.entry_date).days,
                ))
                position = None
                last_close_idx = i
                max_adverse = 0.0
            continue

        # --- Entry Logic ---
        if (i - last_close_idx) < params.cooldown_days:
            continue

        if sigma <= 0:
            continue

        T = target_dte / 365.0
        if T <= 0:
            continue

        try:
            short_put = find_strike_for_delta(price, T, RISK_FREE_RATE, sigma, put_delta, "put")
            short_call = find_strike_for_delta(price, T, RISK_FREE_RATE, sigma, call_delta, "call")
            long_put = short_put - params.spread_width
            long_call = short_call + params.spread_width

            temp_pos = BacktestPosition(
                symbol=symbol, entry_date=today_date,
                expiry_date=today_date + timedelta(days=target_dte),
                entry_dte=target_dte,
                short_put_strike=short_put, long_put_strike=long_put,
                short_call_strike=short_call, long_call_strike=long_call,
                entry_credit=0.0, entry_vix=current_vix,
            )
            entry_credit = _price_ic(price, temp_pos, target_dte, sigma)

            if entry_credit <= 0:
                continue

            position = BacktestPosition(
                symbol=symbol,
                entry_date=today_date,
                expiry_date=today_date + timedelta(days=target_dte),
                entry_dte=target_dte,
                short_put_strike=short_put,
                long_put_strike=long_put,
                short_call_strike=short_call,
                long_call_strike=long_call,
                entry_credit=entry_credit,
                entry_vix=current_vix,
                entry_vix9d=current_vix9d,
                entry_term_ratio=term_ratio,
                entry_bull_share=bull_share,
                entry_indicator_votes=indicator_votes,
            )
            max_adverse = 0.0
        except Exception as e:
            logger.debug(f"Entry failed on {today}: {e}")

    # Close any remaining position at last day
    if position is not None:
        last_price = float(ohlcv.iloc[-1]["close"])
        last_date = dates[-1].date() if hasattr(dates[-1], "date") else dates[-1]
        dte_remaining = max((position.expiry_date - last_date).days, 0)
        current_value = _price_ic(last_price, position, dte_remaining, sigma)
        pnl = position.entry_credit - current_value
        max_risk = params.spread_width
        results.append(TradeResult(
            position=position, exit_date=last_date, exit_value=current_value,
            pnl=pnl, pnl_pct=pnl / max_risk if max_risk > 0 else 0.0,
            exit_reason="end_of_data", max_adverse_excursion=max_adverse,
            days_held=(last_date - position.entry_date).days,
        ))

    logger.info(f"{symbol}: {len(results)} trades simulated")
    return results


def compute_metrics(results: list[TradeResult]) -> dict:
    """Compute standard backtest metrics from trade results."""
    if not results:
        return {
            "total_trades": 0, "win_rate": 0.0, "total_pnl": 0.0,
            "avg_win": 0.0, "avg_loss": 0.0, "max_drawdown": 0.0, "sharpe_ratio": 0.0,
        }

    pnls = [r.pnl for r in results]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    cum_pnl = np.cumsum(pnls)
    peak = np.maximum.accumulate(cum_pnl)
    drawdown = peak - cum_pnl
    max_dd = float(np.max(drawdown)) if len(drawdown) > 0 else 0.0

    pnl_arr = np.array(pnls)
    sharpe = 0.0
    if len(pnl_arr) > 1 and np.std(pnl_arr) > 0:
        trades_per_year = max(len(results) / 5.0, 1)
        sharpe = float(np.mean(pnl_arr) / np.std(pnl_arr) * np.sqrt(trades_per_year))

    return {
        "total_trades": len(results),
        "win_rate": len(wins) / len(results) if results else 0.0,
        "total_pnl": round(sum(pnls), 2),
        "avg_win": round(sum(wins) / len(wins), 2) if wins else 0.0,
        "avg_loss": round(sum(losses) / len(losses), 2) if losses else 0.0,
        "max_drawdown": round(max_dd, 2),
        "sharpe_ratio": round(sharpe, 3),
    }
