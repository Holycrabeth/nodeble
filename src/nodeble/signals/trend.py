# -*- coding: utf-8 -*-
"""Trend indicators (5): SMA Cross, EMA Cross, ADX, Supertrend, Aroon."""

import numpy as np
import pandas as pd

from nodeble.signals.base import BaseIndicator


class SMACross(BaseIndicator):
    """SMA 50/200 Golden/Death Cross.

    With confirmation_bars > 0, requires the signal direction to be consistent
    for the last N bars before returning it. Otherwise returns 0 (neutral).
    """

    name = "sma_50_200_cross"
    category = "trend"
    warmup_bars = 200

    def __init__(self, confirmation_bars: int = 0):
        self.confirmation_bars = confirmation_bars

    def compute(self, df: pd.DataFrame) -> int:
        close = df["close"]
        sma50 = close.rolling(50).mean()
        sma200 = close.rolling(200).mean()

        if self.confirmation_bars <= 0:
            return 1 if sma50.iloc[-1] > sma200.iloc[-1] else -1

        diff = sma50 - sma200
        current_signal = 1 if diff.iloc[-1] > 0 else -1
        for i in range(1, self.confirmation_bars + 1):
            if len(diff) < i + 1:
                return 0
            bar_signal = 1 if diff.iloc[-(i + 1)] > 0 else -1
            if bar_signal != current_signal:
                return 0
        return current_signal


class EMACross(BaseIndicator):
    """EMA 12/26 Cross.

    With confirmation_bars > 0, requires consistent signal for N bars.
    """

    name = "ema_12_26_cross"
    category = "trend"
    warmup_bars = 26

    def __init__(self, confirmation_bars: int = 0):
        self.confirmation_bars = confirmation_bars

    def compute(self, df: pd.DataFrame) -> int:
        close = df["close"]
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()

        if self.confirmation_bars <= 0:
            return 1 if ema12.iloc[-1] > ema26.iloc[-1] else -1

        diff = ema12 - ema26
        current_signal = 1 if diff.iloc[-1] > 0 else -1
        for i in range(1, self.confirmation_bars + 1):
            if len(diff) < i + 1:
                return 0
            bar_signal = 1 if diff.iloc[-(i + 1)] > 0 else -1
            if bar_signal != current_signal:
                return 0
        return current_signal


class ADXTrend(BaseIndicator):
    """ADX Trend Strength with +DI/-DI direction.

    Supports adaptive threshold for ADX strength via rolling percentile
    when adaptive=True. Only the ADX strength threshold is adaptive;
    the DI comparison is always directional.
    Default constructor reproduces exact original behavior (fixed 25).
    """

    name = "adx_trend"
    category = "trend"
    warmup_bars = 28

    def __init__(
        self,
        adaptive: bool = False,
        lookback: int = 252,
        pctile_high: float = 75.0,
        floor_high: float = 20.0,
        fixed_high: float = 25.0,
    ):
        self.adaptive = adaptive
        self.lookback = lookback
        self.pctile_high = pctile_high
        self.floor_high = floor_high
        self.fixed_high = fixed_high

    @staticmethod
    def _compute_adx(df: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
        """Return (adx, plus_di, minus_di) series."""
        high = df["high"]
        low = df["low"]
        close = df["close"]
        period = 14

        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ], axis=1).max(axis=1)

        up_move = high - high.shift(1)
        down_move = low.shift(1) - low
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        atr = pd.Series(tr, index=df.index).rolling(period).mean()
        plus_di = 100 * pd.Series(plus_dm, index=df.index).rolling(period).mean() / atr
        minus_di = 100 * pd.Series(minus_dm, index=df.index).rolling(period).mean() / atr

        di_sum = plus_di + minus_di
        dx = 100 * (plus_di - minus_di).abs() / di_sum.replace(0, np.nan)
        adx = dx.rolling(period).mean()
        return adx, plus_di, minus_di

    def _adaptive_threshold(self, adx_series: pd.Series) -> float:
        valid = adx_series.dropna()
        if len(valid) < 50:
            return self.fixed_high
        window = valid.iloc[-self.lookback:]
        return max(np.percentile(window, self.pctile_high), self.floor_high)

    def compute(self, df: pd.DataFrame) -> int:
        adx, plus_di, minus_di = self._compute_adx(df)
        last_adx = adx.iloc[-1]
        last_plus = plus_di.iloc[-1]
        last_minus = minus_di.iloc[-1]

        if pd.isna(last_adx):
            return 0

        if self.adaptive:
            strength_thresh = self._adaptive_threshold(adx)
        else:
            strength_thresh = self.fixed_high

        if last_adx > strength_thresh and last_plus > last_minus:
            return 1
        if last_adx > strength_thresh and last_minus > last_plus:
            return -1
        return 0


class Supertrend(BaseIndicator):
    """Supertrend (ATR-based trailing stop).

    With confirmation_bars > 0, requires consistent signal for N bars.
    """

    name = "supertrend"
    category = "trend"
    warmup_bars = 14

    def __init__(self, confirmation_bars: int = 0):
        self.confirmation_bars = confirmation_bars

    def _compute_series(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        """Compute supertrend + close arrays."""
        period = 10
        multiplier = 3.0
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values

        # ATR
        tr = np.maximum(high - low,
                        np.maximum(np.abs(high - np.roll(close, 1)),
                                   np.abs(low - np.roll(close, 1))))
        tr[0] = high[0] - low[0]
        atr = pd.Series(tr).rolling(period).mean().values

        hl2 = (high + low) / 2
        upper_band = hl2 + multiplier * atr
        lower_band = hl2 - multiplier * atr

        supertrend = np.zeros(len(close))
        direction = np.ones(len(close))  # 1 = uptrend

        for i in range(1, len(close)):
            if np.isnan(atr[i]):
                supertrend[i] = supertrend[i - 1]
                direction[i] = direction[i - 1]
                continue

            # Adjust bands
            if lower_band[i] > 0 and lower_band[i - 1] > 0:
                lower_band[i] = max(lower_band[i], lower_band[i - 1]) if close[i - 1] > lower_band[i - 1] else lower_band[i]
            if upper_band[i] > 0 and upper_band[i - 1] > 0:
                upper_band[i] = min(upper_band[i], upper_band[i - 1]) if close[i - 1] < upper_band[i - 1] else upper_band[i]

            if direction[i - 1] == 1:  # was uptrend
                if close[i] < lower_band[i]:
                    direction[i] = -1
                    supertrend[i] = upper_band[i]
                else:
                    direction[i] = 1
                    supertrend[i] = lower_band[i]
            else:  # was downtrend
                if close[i] > upper_band[i]:
                    direction[i] = 1
                    supertrend[i] = lower_band[i]
                else:
                    direction[i] = -1
                    supertrend[i] = upper_band[i]

        return close, supertrend

    def compute(self, df: pd.DataFrame) -> int:
        close, supertrend = self._compute_series(df)

        if self.confirmation_bars <= 0:
            return 1 if close[-1] > supertrend[-1] else -1

        current_signal = 1 if close[-1] > supertrend[-1] else -1
        for i in range(1, self.confirmation_bars + 1):
            idx = -(i + 1)
            if abs(idx) > len(close):
                return 0
            bar_signal = 1 if close[idx] > supertrend[idx] else -1
            if bar_signal != current_signal:
                return 0
        return current_signal


class AroonOscillator(BaseIndicator):
    """Aroon Oscillator.

    With confirmation_bars > 0, requires the signal (threshold-based, can be 0)
    to be consistent for N bars before returning it. On inconsistency returns 0.
    """

    name = "aroon_oscillator"
    category = "trend"
    warmup_bars = 25

    def __init__(self, confirmation_bars: int = 0):
        self.confirmation_bars = confirmation_bars

    def _signal_at(self, aroon_up: pd.Series, aroon_down: pd.Series, idx: int) -> int:
        osc = aroon_up.iloc[idx] - aroon_down.iloc[idx]
        if osc > 50:
            return 1
        if osc < -50:
            return -1
        return 0

    def compute(self, df: pd.DataFrame) -> int:
        period = 25
        high = df["high"]
        low = df["low"]

        aroon_up = high.rolling(period + 1).apply(
            lambda x: x.argmax() / period * 100, raw=True
        )
        aroon_down = low.rolling(period + 1).apply(
            lambda x: x.argmin() / period * 100, raw=True
        )

        current_signal = self._signal_at(aroon_up, aroon_down, -1)

        if self.confirmation_bars <= 0 or current_signal == 0:
            return current_signal

        for i in range(1, self.confirmation_bars + 1):
            idx = -(i + 1)
            if abs(idx) > len(aroon_up):
                return 0
            bar_signal = self._signal_at(aroon_up, aroon_down, idx)
            if bar_signal != current_signal:
                return 0
        return current_signal
