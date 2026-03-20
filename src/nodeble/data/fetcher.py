# -*- coding: utf-8 -*-
"""Data fetcher: Tiger API primary, yfinance fallback."""

import logging
from datetime import date

import pandas as pd

logger = logging.getLogger(__name__)

EXPECTED_COLS = ["open", "high", "low", "close", "volume"]


class DataFetcher:
    """Retrieve daily OHLCV bars from Tiger API or yfinance."""

    def __init__(self, broker=None):
        self._broker = broker

    def get_daily_bars(
        self, symbol: str, start_date, end_date
    ) -> pd.DataFrame:
        """Fetch daily bars for a single symbol.

        Tries Tiger API first, falls back to yfinance.
        Returns DataFrame with DatetimeIndex and columns [open, high, low, close, volume].
        """
        df = None

        # Try Tiger API
        if self._broker is not None:
            try:
                df = self._fetch_tiger(symbol, start_date, end_date)
            except Exception as e:
                logger.warning(f"Tiger API failed for {symbol}: {e}")
                df = None

        # Fallback to yfinance
        if df is None:
            try:
                df = self._fetch_yfinance(symbol, start_date, end_date)
            except Exception as e:
                logger.error(f"yfinance also failed for {symbol}: {e}")
                return pd.DataFrame(columns=EXPECTED_COLS)

        df = self._validate(df, symbol)
        return df

    def get_daily_bars_batch(
        self, symbols: list[str], start_date, end_date
    ) -> dict[str, pd.DataFrame]:
        """Fetch daily bars for multiple symbols. Logs failures, does not abort."""
        results = {}
        for sym in symbols:
            try:
                results[sym] = self.get_daily_bars(sym, start_date, end_date)
            except Exception as e:
                logger.error(f"Failed to fetch {sym}: {e}")
        return results

    def _fetch_tiger(self, symbol: str, start_date, end_date) -> pd.DataFrame:
        raw = self._broker.get_historical_bars(
            symbols=[symbol],
            period="day",
            begin_time=str(start_date),
            end_time=str(end_date),
            limit=600,
        )

        if raw is None or (isinstance(raw, pd.DataFrame) and raw.empty):
            raise ValueError(f"Tiger returned no data for {symbol}")

        df = raw.copy()

        if "time" in df.columns:
            df["date"] = pd.to_datetime(df["time"], unit="ms", utc=True)
            df["date"] = df["date"].dt.tz_convert("America/New_York").dt.normalize()
            df = df.set_index("date")
            df.index = df.index.tz_localize(None)

        col_map = {c: c.lower() for c in df.columns}
        df = df.rename(columns=col_map)
        df = df[EXPECTED_COLS]
        return df

    def _fetch_yfinance(self, symbol: str, start_date, end_date) -> pd.DataFrame:
        import yfinance as yf

        logger.info(f"Fetching {symbol} from yfinance")
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=str(start_date), end=str(end_date), auto_adjust=True)

        if df.empty:
            raise ValueError(f"yfinance returned no data for {symbol}")

        col_map = {
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
        df = df.rename(columns=col_map)
        df = df[EXPECTED_COLS]
        df.index = df.index.tz_localize(None)
        df.index.name = "date"
        return df

    def _validate(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        if df.empty:
            return df

        before = len(df)
        df = df.dropna(subset=EXPECTED_COLS)
        dropped = before - len(df)
        if dropped:
            logger.warning(f"{symbol}: dropped {dropped} rows with NaN values")

        df = df[df["volume"] > 0]
        df = df.sort_index()
        return df
