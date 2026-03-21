# -*- coding: utf-8 -*-
"""Volatility indicators (5): Bollinger, Keltner, ATR Trend, Donchian, BB Width."""

import numpy as np
import pandas as pd

from nodeble.signals.base import BaseIndicator


class BollingerBandPosition(BaseIndicator):
    """Bollinger Band Position — close relative to bands."""

    name = "bollinger_position"
    category = "volatility"
    warmup_bars = 20

    def compute(self, df: pd.DataFrame) -> int:
        period = 20
        mult = 2.0
        close = df["close"]
        sma = close.rolling(period).mean()
        std = close.rolling(period).std()
        upper = sma + mult * std
        lower = sma - mult * std

        last_close = close.iloc[-1]
        if last_close < lower.iloc[-1]:
            return 1  # below lower band → oversold, bullish
        if last_close > upper.iloc[-1]:
            return -1  # above upper band → overbought, bearish
        return 0


class KeltnerChannel(BaseIndicator):
    """Keltner Channel — close relative to ATR-based bands."""

    name = "keltner_channel"
    category = "volatility"
    warmup_bars = 20

    def compute(self, df: pd.DataFrame) -> int:
        period = 20
        mult = 1.5
        close = df["close"]
        high = df["high"]
        low = df["low"]

        ema = close.ewm(span=period, adjust=False).mean()

        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()

        upper = ema + mult * atr
        lower = ema - mult * atr

        last_close = close.iloc[-1]
        if last_close < lower.iloc[-1]:
            return 1
        if last_close > upper.iloc[-1]:
            return -1
        return 0


class ATRTrend(BaseIndicator):
    """ATR Trend — volatility contraction/expansion + price direction."""

    name = "atr_trend"
    category = "volatility"
    warmup_bars = 20

    def compute(self, df: pd.DataFrame) -> int:
        period = 14
        sma_period = 20
        close = df["close"]
        high = df["high"]
        low = df["low"]

        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()

        sma20 = close.rolling(sma_period).mean()

        # ATR decreasing = volatility contracting
        atr_decreasing = atr.iloc[-1] < atr.iloc[-5]  # compare to 5 bars ago
        atr_increasing = atr.iloc[-1] > atr.iloc[-5]

        above_sma = close.iloc[-1] > sma20.iloc[-1]
        below_sma = close.iloc[-1] < sma20.iloc[-1]

        if atr_decreasing and above_sma:
            return 1  # low vol + uptrend = bullish
        if atr_increasing and below_sma:
            return -1  # high vol + downtrend = bearish
        return 0


class DonchianChannel(BaseIndicator):
    """Donchian Channel — breakout at 20-day highs/lows.

    With confirmation_bars > 0, requires consistent signal for N bars.
    """

    name = "donchian_channel"
    category = "volatility"
    warmup_bars = 20

    def __init__(self, confirmation_bars: int = 0):
        self.confirmation_bars = confirmation_bars

    def _signal_at(self, close: pd.Series, high_max: pd.Series, low_min: pd.Series, idx: int) -> int:
        c = close.iloc[idx]
        tol = c * 0.001
        if c >= high_max.iloc[idx] - tol:
            return 1
        if c <= low_min.iloc[idx] + tol:
            return -1
        return 0

    def compute(self, df: pd.DataFrame) -> int:
        period = 20
        close = df["close"]
        high_max = df["high"].rolling(period).max()
        low_min = df["low"].rolling(period).min()

        current_signal = self._signal_at(close, high_max, low_min, -1)

        if self.confirmation_bars <= 0 or current_signal == 0:
            return current_signal

        for i in range(1, self.confirmation_bars + 1):
            idx = -(i + 1)
            if abs(idx) > len(close):
                return 0
            bar_signal = self._signal_at(close, high_max, low_min, idx)
            if bar_signal != current_signal:
                return 0
        return current_signal


class BollingerBandWidth(BaseIndicator):
    """Bollinger Band Width squeeze → breakout."""

    name = "bollinger_width"
    category = "volatility"
    warmup_bars = 20

    def compute(self, df: pd.DataFrame) -> int:
        period = 20
        mult = 2.0
        close = df["close"]
        sma = close.rolling(period).mean()
        std = close.rolling(period).std()
        upper = sma + mult * std
        lower = sma - mult * std

        # Bandwidth = (upper - lower) / sma
        bw = (upper - lower) / sma

        if len(bw) < 6:
            return 0

        # Squeeze → expansion: width was contracting, now expanding
        bw_expanding = bw.iloc[-1] > bw.iloc[-5]
        bw_was_low = bw.iloc[-5] < bw.rolling(120, min_periods=20).mean().iloc[-5]

        if bw_expanding and bw_was_low:
            last_close = close.iloc[-1]
            if last_close > upper.iloc[-1]:
                return 1  # breakout upward from squeeze
            if last_close < lower.iloc[-1]:
                return -1  # breakout downward from squeeze
        return 0
