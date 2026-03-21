# -*- coding: utf-8 -*-
"""Fetch and cache historical data for backtesting."""
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

from nodeble.paths import get_data_dir

logger = logging.getLogger(__name__)

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


def _fetch_and_cache(ticker: str, filename: str, start: str, end: str, force: bool = False) -> pd.DataFrame:
    """Fetch from yfinance, cache to Parquet."""
    cache_path = _get_cache_dir() / filename

    if cache_path.exists() and not force:
        age_hours = (pd.Timestamp.now() - pd.Timestamp(cache_path.stat().st_mtime, unit="s")).total_seconds() / 3600
        if age_hours < 24:
            logger.info(f"Using cached {filename} ({age_hours:.1f}h old)")
            return pd.read_parquet(cache_path)

    logger.info(f"Fetching {ticker} from yfinance ({start} to {end})...")
    t = yf.Ticker(ticker)
    df = t.history(start=start, end=end, auto_adjust=True)

    if df.empty:
        logger.warning(f"No data returned for {ticker}")
        return pd.DataFrame()

    col_map = {"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
    df = df.rename(columns=col_map)
    cols = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
    df = df[cols]
    df.index = df.index.tz_localize(None) if df.index.tz is not None else df.index
    df.index.name = "date"

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
