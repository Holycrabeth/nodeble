# -*- coding: utf-8 -*-
"""Parquet-based local cache for OHLCV data. One file per symbol."""

import logging
import time
from pathlib import Path

import pandas as pd

from nodeble.paths import get_data_dir

logger = logging.getLogger(__name__)


class DataCache:
    """Per-symbol Parquet cache with staleness check."""

    def __init__(self, cache_dir: str | None = None):
        if cache_dir is None:
            self._dir = get_data_dir() / "data" / "cache"
        else:
            self._dir = Path(cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, symbol: str) -> Path:
        return self._dir / f"{symbol}.parquet"

    def get(self, symbol: str, start_date, end_date) -> pd.DataFrame | None:
        """Return cached bars for [start_date, end_date], or None if not available."""
        p = self._path(symbol)
        if not p.exists():
            return None

        df = pd.read_parquet(p)
        if df.empty:
            return None

        # Strip timezone from index if present (handles legacy tz-aware parquets)
        if hasattr(df.index, "tz") and df.index.tz is not None:
            df.index = df.index.tz_localize(None)

        # Filter to requested range
        mask = (df.index >= pd.Timestamp(start_date)) & (
            df.index <= pd.Timestamp(end_date)
        )
        subset = df.loc[mask]

        if subset.empty:
            return None

        # Check if cache covers the requested range (within 1 trading day tolerance)
        cached_start = subset.index.min().date()
        cached_end = subset.index.max().date()
        req_start = pd.Timestamp(start_date).date()
        req_end = pd.Timestamp(end_date).date()

        # Allow 5 day tolerance on edges (weekends + holidays)
        from datetime import timedelta

        if cached_start > req_start + timedelta(days=5):
            return None
        if cached_end < req_end - timedelta(days=5):
            return None

        return subset

    def put(self, symbol: str, df: pd.DataFrame) -> None:
        """Merge new data with existing cache file, deduplicate by date."""
        if df.empty:
            return

        p = self._path(symbol)
        if p.exists():
            existing = pd.read_parquet(p)
            if hasattr(existing.index, "tz") and existing.index.tz is not None:
                existing.index = existing.index.tz_localize(None)
            df = pd.concat([existing, df])
            df = df[~df.index.duplicated(keep="last")]
            df = df.sort_index()

        df.to_parquet(p, engine="pyarrow")
        logger.info(f"Cache updated: {symbol} ({len(df)} bars)")

    def is_stale(self, symbol: str, max_age_hours: float = 18) -> bool:
        """True if cache file is missing or older than max_age_hours."""
        p = self._path(symbol)
        if not p.exists():
            return True
        age_hours = (time.time() - p.stat().st_mtime) / 3600
        return age_hours > max_age_hours

    def get_or_fetch(self, symbol: str, start_date, end_date, fetcher) -> pd.DataFrame:
        """Return cached data if fresh and covers range, else fetch+cache+return."""
        if not self.is_stale(symbol):
            cached = self.get(symbol, start_date, end_date)
            if cached is not None:
                logger.debug(f"Cache hit: {symbol}")
                return cached

        # Fetch fresh data
        df = fetcher.get_daily_bars(symbol, start_date, end_date)
        if df is not None and not df.empty:
            self.put(symbol, df)
        return df
