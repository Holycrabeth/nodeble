# -*- coding: utf-8 -*-
"""Shared option chain screening utilities.

Extracted from options/scanner.py and theta/scanner.py to centralize:
- IV rank screening
- Earnings blackout detection
- Expiry selection
- Chain + price fetching
"""

import logging
from datetime import date, timedelta

import numpy as np

logger = logging.getLogger(__name__)


def screen_symbol_iv(broker, symbols: list[str]) -> tuple[dict[str, float], list]:
    """Batch IV rank screening. Returns ({symbol: iv_rank}, raw_analyses)."""
    iv_map: dict[str, float] = {}
    analyses = []
    try:
        analyses = broker.get_option_analysis(symbols)
    except Exception as e:
        logger.error(f"IV analysis failed for {len(symbols)} symbols: {e}")
        return iv_map, analyses

    for a in analyses:
        sym = getattr(a, "symbol", "")
        iv_metric = getattr(a, "iv_metric", None)
        if iv_metric is not None:
            rank = getattr(iv_metric, "rank", None)
            if rank is not None:
                iv_map[sym] = float(rank)
    return iv_map, analyses


def compute_iv_rv_ratios(
    analyses: list,
    symbols: list[str],
    lookback_days: int = 20,
) -> dict[str, dict]:
    """Batch IV/RV ratio computation for multiple symbols.

    For each symbol:
    1. Extract ATM implied vol from already-fetched analyses (implied_vol_30_days)
    2. Calculate 20-day realized vol from daily close prices: std(log_returns) * sqrt(252)
    3. Return ratio = IV / RV

    Args:
        analyses: Raw analysis objects from broker.get_option_analysis() (passed from screen_symbol_iv).
        symbols: Symbols to compute for (filters analyses list).
        lookback_days: Trading days for RV calculation.

    Returns: {symbol: {"iv": float, "rv": float, "ratio": float}}
    Symbols where calculation fails are omitted (fail-open).
    """
    result: dict[str, dict] = {}

    # Extract IV from already-fetched analyses (no duplicate API call)
    iv_30d: dict[str, float] = {}
    symbols_set = set(symbols)
    for a in (analyses or []):
        sym = getattr(a, "symbol", "")
        if sym not in symbols_set:
            continue
        iv_val = getattr(a, "implied_vol_30_days", None)
        if isinstance(iv_val, (int, float)) and iv_val > 0:
            iv_30d[sym] = float(iv_val)

    if not iv_30d:
        return result

    # Compute RV for symbols that have IV
    from nodeble.data.cache import DataCache
    cache = DataCache()
    today = date.today()
    start = today - timedelta(days=int(lookback_days * 2))  # extra calendar days for ~20 trading days

    for sym in iv_30d:
        try:
            df = cache.get(sym, start, today)
            if df is None or len(df) < 5:
                continue
            closes = df["close"].values
            # Use last lookback_days trading days
            closes = closes[-lookback_days:] if len(closes) > lookback_days else closes
            if len(closes) < 5:
                continue
            log_returns = np.log(closes[1:] / closes[:-1])
            rv = float(np.std(log_returns) * np.sqrt(252))
            iv = iv_30d[sym]
            ratio = iv / rv if rv > 0 else None
            if ratio is not None:
                result[sym] = {"iv": iv, "rv": rv, "ratio": ratio}
        except Exception as e:
            logger.debug(f"RV computation failed for {sym}: {e}")

    return result


def check_write_when(
    symbol: str,
    right: str,
    stock_price: float,
    config: dict,
) -> tuple[bool, str, float]:
    """Check if market direction favors writing this option type.

    Args:
        symbol: Underlying symbol.
        right: "put" (selling puts) or "call" (selling calls).
        stock_price: Current live price from broker.
        config: write_when config dict.

    Returns:
        (passes, reason, change_pct)
    """
    from nodeble.data.cache import DataCache

    cache = DataCache()
    today = date.today()
    start = today - timedelta(days=5)
    df = cache.get(symbol, start, today)

    if df is None or len(df) < 2:
        return (True, "no_prev_close_data", 0.0)

    prev_close = float(df["close"].iloc[-1])
    if prev_close <= 0:
        return (True, "invalid_prev_close", 0.0)

    change_pct = (stock_price - prev_close) / prev_close
    is_green = change_pct > 0
    is_red = change_pct < 0

    if right == "put":
        can_green = config.get("puts", {}).get("green", True)
        can_red = config.get("puts", {}).get("red", True)
    elif right == "call":
        can_green = config.get("calls", {}).get("green", True)
        can_red = config.get("calls", {}).get("red", True)
    else:
        return (True, "unknown_right", change_pct)

    if is_green and not can_green:
        return (False, f"green day ({change_pct:+.1%}) — {right} writing disabled on green", change_pct)
    if is_red and not can_red:
        return (False, f"red day ({change_pct:+.1%}) — {right} writing disabled on red", change_pct)

    # Sigma threshold (optional)
    threshold_sigma = config.get("threshold_sigma", 0)
    if threshold_sigma > 0:
        lookback = config.get("sigma_lookback_days", 30)
        lookback_start = today - timedelta(days=int(lookback * 2))
        hist = cache.get(symbol, lookback_start, today)
        if hist is not None and len(hist) >= 5:
            closes = hist["close"].values[-lookback:] if len(hist) > lookback else hist["close"].values
            if len(closes) >= 5:
                log_returns = np.log(closes[1:] / closes[:-1])
                daily_sigma = float(np.std(log_returns))
                if abs(change_pct) < daily_sigma * threshold_sigma:
                    return (False, f"move {abs(change_pct):.1%} < {threshold_sigma}σ ({daily_sigma * threshold_sigma:.1%})", change_pct)

    return (True, "passes", change_pct)


def check_cooldown(
    symbol: str,
    positions: dict,
    cooldown_days: int,
    ref_date: date | None = None,
) -> tuple[bool, str]:
    """Check if a symbol is in cooldown (recently had a position opened).

    Args:
        symbol: Underlying symbol.
        positions: State positions dict (values must have .underlying and .entry_date attrs).
        cooldown_days: Number of days to wait after opening. 0 = disabled.
        ref_date: Reference date (default: today). For testing.

    Returns:
        (allowed, reason)
    """
    if cooldown_days <= 0:
        return (True, "cooldown disabled")

    today = ref_date or date.today()
    cutoff = today - timedelta(days=cooldown_days)
    cutoff_str = cutoff.isoformat()

    for pos in positions.values():
        underlying = getattr(pos, "underlying", "")
        entry_date = getattr(pos, "entry_date", "") or getattr(pos, "leaps_entry_date", "")
        if underlying == symbol and entry_date and entry_date >= cutoff_str:
            days_ago = (today - date.fromisoformat(entry_date)).days
            return (False, f"position opened {days_ago}d ago ({entry_date}), cooldown {cooldown_days}d")

    return (True, "no recent positions")


def is_earnings_blackout(symbol: str, blackout_days: int = 7) -> bool:
    """Check if symbol is within earnings blackout window.

    Fail-closed: if we can't determine, block trading.
    Selling options into earnings = max loss risk.
    """
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        cal = ticker.calendar
        if cal is None or (hasattr(cal, "empty") and cal.empty):
            return False
        if isinstance(cal, dict):
            earnings_date = cal.get("Earnings Date")
            if isinstance(earnings_date, list) and earnings_date:
                earnings_date = earnings_date[0]
        else:
            if "Earnings Date" in cal.index:
                earnings_date = cal.loc["Earnings Date"].iloc[0]
            else:
                return False

        if earnings_date is None:
            return False

        if hasattr(earnings_date, "date"):
            earnings_date = earnings_date.date()
        elif isinstance(earnings_date, str):
            earnings_date = date.fromisoformat(earnings_date)

        today = date.today()
        days_until = (earnings_date - today).days
        if 0 <= days_until <= blackout_days:
            logger.info(f"{symbol}: earnings in {days_until} days — blackout")
            return True
    except Exception as e:
        logger.warning(f"Earnings check failed for {symbol} (blocking — fail-closed): {e}")
        return True
    return False


def select_best_expiry(
    expirations: list[dict],
    dte_min: int = 7,
    dte_max: int = 14,
    dte_ideal: int = 10,
    prefer_monthly: bool = False,
    ref_date: date | None = None,
) -> str | None:
    """Select best expiry within DTE range, closest to dte_ideal."""
    ranked = select_ranked_expiries(
        expirations, dte_min, dte_max, dte_ideal, prefer_monthly, ref_date,
    )
    return ranked[0] if ranked else None


def select_ranked_expiries(
    expirations: list[dict],
    dte_min: int = 7,
    dte_max: int = 14,
    dte_ideal: int = 10,
    prefer_monthly: bool = False,
    ref_date: date | None = None,
    max_results: int = 3,
) -> list[str]:
    """Return up to max_results expiries within DTE range, diversified by DTE.

    Strategy:
      1. Best expiry closest to dte_ideal (original behavior)
      2. A monthly expiry if available (best liquidity)
      3. An expiry from a different DTE zone (spread out the search)

    This avoids trying 3 adjacent weeklies that all have the same poor liquidity.
    """
    if ref_date is None:
        ref_date = date.today()

    valid = []
    for exp in expirations:
        exp_date_str = exp.get("date", "")
        try:
            exp_date = date.fromisoformat(exp_date_str[:10])
        except ValueError:
            continue
        dte = (exp_date - ref_date).days
        if dte_min <= dte <= dte_max:
            valid.append({
                "date": exp_date_str[:10],
                "dte": dte,
                "is_monthly": exp.get("period_tag", "").lower() in ("monthly", "month"),
            })

    if not valid:
        return []

    # Sort by: monthly preference, then distance from ideal
    valid.sort(key=lambda e: (
        0 if (prefer_monthly and e["is_monthly"]) else 1,
        abs(e["dte"] - dte_ideal),
    ))

    # Build diversified result list
    result = [valid[0]["date"]]
    used_dtes = {valid[0]["dte"]}

    # Prioritize monthly expiries as fallback (best OI)
    for e in valid:
        if len(result) >= max_results:
            break
        if e["date"] in result:
            continue
        if e["is_monthly"]:
            result.append(e["date"])
            used_dtes.add(e["dte"])

    # Fill remaining slots with expiries at least 5 DTE apart from already-chosen
    for e in valid:
        if len(result) >= max_results:
            break
        if e["date"] in result:
            continue
        if all(abs(e["dte"] - used) >= 5 for used in used_dtes):
            result.append(e["date"])
            used_dtes.add(e["dte"])

    # If still not enough, fill with whatever's left
    for e in valid:
        if len(result) >= max_results:
            break
        if e["date"] not in result:
            result.append(e["date"])

    return result


def fetch_chain_and_price(
    broker,
    symbol: str,
    expiry: str,
    option_filter: dict | None = None,
) -> tuple[list, float]:
    """Fetch option chain and stock price for a symbol/expiry.

    Returns (chain_list, stock_price). Stock price falls back to 0.0.
    Raises on chain fetch error.
    """
    chain = broker.get_option_chain(
        symbol=symbol,
        expiry=expiry,
        option_filter=option_filter or {},
    )

    # 3-tier fallback: Tiger API → yfinance → Parquet cache
    stock_price = broker.get_stock_price(symbol)

    return chain, stock_price
