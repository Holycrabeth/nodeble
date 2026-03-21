# -*- coding: utf-8 -*-
"""Momentum indicators (5): RSI, MACD, Stochastic, CCI, Williams %R."""

import numpy as np
import pandas as pd

from nodeble.signals.base import BaseIndicator


class RSI(BaseIndicator):
    """RSI 14 — oversold bounce / overbought reversal.

    Supports adaptive thresholds via rolling percentile when adaptive=True.
    Default constructor reproduces exact original behavior (fixed 30/70).
    """

    name = "rsi_14"
    category = "momentum"
    warmup_bars = 14

    def __init__(
        self,
        adaptive: bool = False,
        lookback: int = 252,
        pctile_low: float = 10.0,
        pctile_high: float = 90.0,
        floor_low: float = 20.0,
        ceil_high: float = 80.0,
        fixed_low: float = 30.0,
        fixed_high: float = 70.0,
    ):
        self.adaptive = adaptive
        self.lookback = lookback
        self.pctile_low = pctile_low
        self.pctile_high = pctile_high
        self.floor_low = floor_low
        self.ceil_high = ceil_high
        self.fixed_low = fixed_low
        self.fixed_high = fixed_high

    @staticmethod
    def _compute_rsi(close: pd.Series) -> pd.Series:
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _adaptive_thresholds(self, rsi_series: pd.Series) -> tuple[float, float]:
        valid = rsi_series.dropna()
        if len(valid) < 50:
            return self.fixed_low, self.fixed_high
        window = valid.iloc[-self.lookback:]
        low_thresh = max(np.percentile(window, self.pctile_low), self.floor_low)
        high_thresh = min(np.percentile(window, self.pctile_high), self.ceil_high)
        return low_thresh, high_thresh

    def compute(self, df: pd.DataFrame) -> int:
        rsi = self._compute_rsi(df["close"])
        last = rsi.iloc[-1]

        if pd.isna(last):
            return 0

        if self.adaptive:
            low_thresh, high_thresh = self._adaptive_thresholds(rsi)
        else:
            low_thresh, high_thresh = self.fixed_low, self.fixed_high

        if last < low_thresh:
            return 1  # oversold → bullish
        if last > high_thresh:
            return -1  # overbought → bearish
        return 0


class MACDHistogram(BaseIndicator):
    """MACD Histogram direction."""

    name = "macd_histogram"
    category = "momentum"
    warmup_bars = 35

    def compute(self, df: pd.DataFrame) -> int:
        close = df["close"]
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram = macd_line - signal_line

        if len(histogram) < 2:
            return 0

        last = histogram.iloc[-1]
        prev = histogram.iloc[-2]

        if last > 0 and last > prev:
            return 1  # positive and increasing
        if last < 0 and last < prev:
            return -1  # negative and decreasing
        return 0


class StochasticOscillator(BaseIndicator):
    """Stochastic %K/%D crossover at extremes.

    Supports adaptive thresholds via rolling percentile when adaptive=True.
    Default constructor reproduces exact original behavior (fixed 20/80).
    """

    name = "stochastic_kd"
    category = "momentum"
    warmup_bars = 14

    def __init__(
        self,
        adaptive: bool = False,
        lookback: int = 252,
        pctile_low: float = 10.0,
        pctile_high: float = 90.0,
        floor_low: float = 15.0,
        ceil_high: float = 85.0,
        fixed_low: float = 20.0,
        fixed_high: float = 80.0,
    ):
        self.adaptive = adaptive
        self.lookback = lookback
        self.pctile_low = pctile_low
        self.pctile_high = pctile_high
        self.floor_low = floor_low
        self.ceil_high = ceil_high
        self.fixed_low = fixed_low
        self.fixed_high = fixed_high

    @staticmethod
    def _compute_stoch_k(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        """Return (smoothed %K, %D) series."""
        period = 14
        smooth_k = 3
        smooth_d = 3
        low_min = df["low"].rolling(period).min()
        high_max = df["high"].rolling(period).max()
        denom = (high_max - low_min).replace(0, np.nan)
        fast_k = 100 * (df["close"] - low_min) / denom
        k = fast_k.rolling(smooth_k).mean()
        d = k.rolling(smooth_d).mean()
        return k, d

    def _adaptive_thresholds(self, series: pd.Series) -> tuple[float, float]:
        valid = series.dropna()
        if len(valid) < 50:
            return self.fixed_low, self.fixed_high
        window = valid.iloc[-self.lookback:]
        low_thresh = max(np.percentile(window, self.pctile_low), self.floor_low)
        high_thresh = min(np.percentile(window, self.pctile_high), self.ceil_high)
        return low_thresh, high_thresh

    def compute(self, df: pd.DataFrame) -> int:
        k, d = self._compute_stoch_k(df)
        last_k = k.iloc[-1]
        last_d = d.iloc[-1]

        if pd.isna(last_k) or pd.isna(last_d):
            return 0

        if self.adaptive:
            low_thresh, high_thresh = self._adaptive_thresholds(k)
        else:
            low_thresh, high_thresh = self.fixed_low, self.fixed_high

        if last_k < low_thresh and last_k > last_d:
            return 1  # oversold, %K crossing above %D
        if last_k > high_thresh and last_k < last_d:
            return -1  # overbought, %K crossing below %D
        return 0


class CCI(BaseIndicator):
    """Commodity Channel Index (20-period).

    Supports adaptive thresholds via rolling percentile when adaptive=True.
    Default constructor reproduces exact original behavior (fixed ±100).
    """

    name = "cci_20"
    category = "momentum"
    warmup_bars = 20

    def __init__(
        self,
        adaptive: bool = False,
        lookback: int = 252,
        pctile_low: float = 10.0,
        pctile_high: float = 90.0,
        floor_low: float = -150.0,
        ceil_high: float = 150.0,
        fixed_low: float = -100.0,
        fixed_high: float = 100.0,
    ):
        self.adaptive = adaptive
        self.lookback = lookback
        self.pctile_low = pctile_low
        self.pctile_high = pctile_high
        self.floor_low = floor_low
        self.ceil_high = ceil_high
        self.fixed_low = fixed_low
        self.fixed_high = fixed_high

    @staticmethod
    def _compute_cci(df: pd.DataFrame) -> pd.Series:
        """Return the CCI series."""
        period = 20
        tp = (df["high"] + df["low"] + df["close"]) / 3
        sma_tp = tp.rolling(period).mean()
        mad = tp.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
        return (tp - sma_tp) / (0.015 * mad.replace(0, np.nan))

    def _adaptive_thresholds(self, series: pd.Series) -> tuple[float, float]:
        valid = series.dropna()
        if len(valid) < 50:
            return self.fixed_low, self.fixed_high
        window = valid.iloc[-self.lookback:]
        low_thresh = max(np.percentile(window, self.pctile_low), self.floor_low)
        high_thresh = min(np.percentile(window, self.pctile_high), self.ceil_high)
        return low_thresh, high_thresh

    def compute(self, df: pd.DataFrame) -> int:
        cci = self._compute_cci(df)
        last = cci.iloc[-1]
        if pd.isna(last):
            return 0

        if self.adaptive:
            low_thresh, high_thresh = self._adaptive_thresholds(cci)
        else:
            low_thresh, high_thresh = self.fixed_low, self.fixed_high

        if last > high_thresh:
            return 1
        if last < low_thresh:
            return -1
        return 0


class WilliamsR(BaseIndicator):
    """Williams %R (14-period).

    Supports adaptive thresholds via rolling percentile when adaptive=True.
    Default constructor reproduces exact original behavior (fixed -80/-20).
    Inverted scale: -100 (oversold) to 0 (overbought).
    """

    name = "williams_r"
    category = "momentum"
    warmup_bars = 14

    def __init__(
        self,
        adaptive: bool = False,
        lookback: int = 252,
        pctile_low: float = 10.0,
        pctile_high: float = 90.0,
        floor_low: float = -85.0,
        ceil_high: float = -15.0,
        fixed_low: float = -80.0,
        fixed_high: float = -20.0,
    ):
        self.adaptive = adaptive
        self.lookback = lookback
        self.pctile_low = pctile_low
        self.pctile_high = pctile_high
        self.floor_low = floor_low
        self.ceil_high = ceil_high
        self.fixed_low = fixed_low
        self.fixed_high = fixed_high

    @staticmethod
    def _compute_williams_r(df: pd.DataFrame) -> pd.Series:
        """Return the Williams %R series."""
        period = 14
        high_max = df["high"].rolling(period).max()
        low_min = df["low"].rolling(period).min()
        return -100 * (high_max - df["close"]) / (high_max - low_min)

    def _adaptive_thresholds(self, series: pd.Series) -> tuple[float, float]:
        valid = series.dropna()
        if len(valid) < 50:
            return self.fixed_low, self.fixed_high
        window = valid.iloc[-self.lookback:]
        low_thresh = max(np.percentile(window, self.pctile_low), self.floor_low)
        high_thresh = min(np.percentile(window, self.pctile_high), self.ceil_high)
        return low_thresh, high_thresh

    def compute(self, df: pd.DataFrame) -> int:
        wr = self._compute_williams_r(df)
        last = wr.iloc[-1]
        if pd.isna(last):
            return 0

        if self.adaptive:
            low_thresh, high_thresh = self._adaptive_thresholds(wr)
        else:
            low_thresh, high_thresh = self.fixed_low, self.fixed_high

        if last > high_thresh:
            return -1  # overbought
        if last < low_thresh:
            return 1  # oversold
        return 0
