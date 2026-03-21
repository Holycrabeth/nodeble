# -*- coding: utf-8 -*-
"""Fetch and cache historical data for backtesting."""
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import requests
import pandas as pd
import yfinance as yf

from nodeble.paths import get_data_dir

logger = logging.getLogger(__name__)

FDS_API_KEY = None  # set via env or config

CACHE_DIR = None


def _get_cache_dir() -> Path:
    global CACHE_DIR
    if CACHE_DIR is None:
        CACHE_DIR = get_data_dir() / "data" / "backtest"
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR


@dataclass
class BacktestData:
    ohlcv: dict[str, pd.DataFrame]
    vix: pd.Series
    vix9d: pd.Series


def _fetch_fds(ticker: str, start: str, end: str) -> pd.DataFrame | None:
    """Fetch OHLCV from financialdatasets.ai API. Returns None on failure."""
    import os
    api_key = FDS_API_KEY or os.environ.get("FDS_API_KEY")
    if not api_key:
        return None

    try:
        resp = requests.get(
            "https://api.financialdatasets.ai/prices/",
            params={"ticker": ticker, "interval": "day", "interval_multiplier": 1,
                    "start_date": start, "end_date": end},
            headers={"X-API-Key": api_key},
            timeout=30,
        )
        if resp.status_code != 200:
            logger.debug(f"FDS returned {resp.status_code} for {ticker}")
            return None

        prices = resp.json().get("prices", [])
        if not prices:
            return None

        df = pd.DataFrame(prices)
        df["date"] = pd.to_datetime(df["time"])
        df = df.set_index("date")
        df.index = df.index.tz_localize(None) if df.index.tz is not None else df.index
        df = df[["open", "high", "low", "close", "volume"]]
        df.index.name = "date"
        logger.info(f"FDS: {len(df)} rows for {ticker}")
        return df
    except Exception as e:
        logger.debug(f"FDS fetch failed for {ticker}: {e}")
        return None


def _fetch_yfinance(ticker: str, start: str, end: str) -> pd.DataFrame:
    """Fetch from yfinance."""
    logger.info(f"Fetching {ticker} from yfinance ({start} to {end})...")
    t = yf.Ticker(ticker)
    df = t.history(start=start, end=end, auto_adjust=True)

    if df.empty:
        return pd.DataFrame()

    col_map = {"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
    df = df.rename(columns=col_map)
    cols = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
    df = df[cols]
    df.index = df.index.tz_localize(None) if df.index.tz is not None else df.index
    df.index.name = "date"
    return df


def _fetch_and_cache(ticker: str, filename: str, start: str, end: str, force: bool = False) -> pd.DataFrame:
    """Fetch from FDS (primary) or yfinance (fallback), cache to Parquet."""
    cache_path = _get_cache_dir() / filename

    if cache_path.exists() and not force:
        cached = pd.read_parquet(cache_path)
        # Check if cache covers the requested range (not just age)
        if len(cached) > 200:
            logger.info(f"Using cached {filename} ({len(cached)} rows)")
            return cached

    # Try FDS first for equity tickers (not VIX)
    df = None
    if not ticker.startswith("^"):
        df = _fetch_fds(ticker, start, end)

    # Fallback to yfinance
    if df is None or df.empty:
        df = _fetch_yfinance(ticker, start, end)

    if df.empty:
        logger.warning(f"No data returned for {ticker}")
        return pd.DataFrame()

    df.to_parquet(cache_path)
    logger.info(f"Cached {len(df)} rows to {filename}")
    return df


def load_backtest_data(symbols: list[str], years: int = 5, force_fetch: bool = False) -> BacktestData:
    """Load all data needed for backtesting."""
    end = date.today()
    start = end - timedelta(days=int(years * 365.25 + 60))
    start_str = str(start)
    end_str = str(end)

    ohlcv = {}
    for sym in symbols:
        df = _fetch_and_cache(sym, f"{sym}_ohlcv.parquet", start_str, end_str, force_fetch)
        if not df.empty:
            ohlcv[sym] = df
        else:
            logger.warning(f"No data for {sym}, skipping")

    vix_df = _fetch_and_cache("^VIX", "VIX_daily.parquet", start_str, end_str, force_fetch)
    vix = vix_df["close"] if not vix_df.empty and "close" in vix_df.columns else pd.Series(dtype=float)

    vix9d_df = _fetch_and_cache("^VIX9D", "VIX9D_daily.parquet", start_str, end_str, force_fetch)
    vix9d = vix9d_df["close"] if not vix9d_df.empty and "close" in vix9d_df.columns else pd.Series(dtype=float)

    logger.info(f"Loaded backtest data: {len(ohlcv)} symbols, VIX {len(vix)} days, VIX9D {len(vix9d)} days")
    return BacktestData(ohlcv=ohlcv, vix=vix, vix9d=vix9d)
