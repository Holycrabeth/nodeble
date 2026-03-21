# -*- coding: utf-8 -*-
"""Volume indicators (5): OBV, MFI, CMF, VWAP Distance, Volume SMA Ratio."""

import numpy as np
import pandas as pd

from nodeble.signals.base import BaseIndicator
from nodeble.signals.volume_filter import filtered_volume


class OBVTrend(BaseIndicator):
    """On-Balance Volume trend via 20-SMA of OBV."""

    name = "obv_trend"
    category = "volume"
    warmup_bars = 40

    def __init__(self, use_filtered_volume: bool = False, volume_ema_span: int = 5):
        self.use_filtered_volume = use_filtered_volume
        self.volume_ema_span = volume_ema_span

    def compute(self, df: pd.DataFrame) -> int:
        close = df["close"]
        volume = df["volume"]
        if self.use_filtered_volume:
            volume = filtered_volume(volume, self.volume_ema_span)

        # OBV: cumulative volume, signed by close direction
        direction = np.sign(close.diff())
        direction.iloc[0] = 0
        obv = (direction * volume).cumsum()

        obv_sma = obv.rolling(20).mean()

        if len(obv_sma.dropna()) < 5:
            return 0

        # OBV SMA trending up or down over last 5 bars
        if obv_sma.iloc[-1] > obv_sma.iloc[-5]:
            return 1
        if obv_sma.iloc[-1] < obv_sma.iloc[-5]:
            return -1
        return 0


class MFI(BaseIndicator):
    """Money Flow Index (14-period).

    Supports adaptive thresholds via rolling percentile when adaptive=True.
    Default constructor reproduces exact original behavior (fixed 20/80).
    """

    name = "mfi_14"
    category = "volume"
    warmup_bars = 14

    def __init__(
        self,
        use_filtered_volume: bool = False,
        volume_ema_span: int = 5,
        adaptive: bool = False,
        lookback: int = 252,
        pctile_low: float = 10.0,
        pctile_high: float = 90.0,
        floor_low: float = 15.0,
        ceil_high: float = 85.0,
        fixed_low: float = 20.0,
        fixed_high: float = 80.0,
    ):
        self.use_filtered_volume = use_filtered_volume
        self.volume_ema_span = volume_ema_span
        self.adaptive = adaptive
        self.lookback = lookback
        self.pctile_low = pctile_low
        self.pctile_high = pctile_high
        self.floor_low = floor_low
        self.ceil_high = ceil_high
        self.fixed_low = fixed_low
        self.fixed_high = fixed_high

    def _compute_mfi(self, df: pd.DataFrame) -> pd.Series:
        """Return the MFI series."""
        period = 14
        tp = (df["high"] + df["low"] + df["close"]) / 3
        volume = df["volume"]
        if self.use_filtered_volume:
            volume = filtered_volume(volume, self.volume_ema_span)
        mf = tp * volume

        pos_mf = pd.Series(
            np.where(tp > tp.shift(1), mf, 0), index=df.index
        )
        neg_mf = pd.Series(
            np.where(tp < tp.shift(1), mf, 0), index=df.index
        )

        pos_sum = pos_mf.rolling(period).sum()
        neg_sum = neg_mf.rolling(period).sum()

        mfr = pos_sum / neg_sum.replace(0, np.nan)
        return 100 - (100 / (1 + mfr))

    def _adaptive_thresholds(self, series: pd.Series) -> tuple[float, float]:
        valid = series.dropna()
        if len(valid) < 50:
            return self.fixed_low, self.fixed_high
        window = valid.iloc[-self.lookback:]
        low_thresh = max(np.percentile(window, self.pctile_low), self.floor_low)
        high_thresh = min(np.percentile(window, self.pctile_high), self.ceil_high)
        return low_thresh, high_thresh

    def compute(self, df: pd.DataFrame) -> int:
        mfi = self._compute_mfi(df)
        last = mfi.iloc[-1]
        if pd.isna(last):
            return 0

        if self.adaptive:
            low_thresh, high_thresh = self._adaptive_thresholds(mfi)
        else:
            low_thresh, high_thresh = self.fixed_low, self.fixed_high

        if last < low_thresh:
            return 1  # oversold
        if last > high_thresh:
            return -1  # overbought
        return 0


class CMF(BaseIndicator):
    """Chaikin Money Flow (20-period)."""

    name = "cmf_20"
    category = "volume"
    warmup_bars = 20

    def __init__(self, use_filtered_volume: bool = False, volume_ema_span: int = 5):
        self.use_filtered_volume = use_filtered_volume
        self.volume_ema_span = volume_ema_span

    def compute(self, df: pd.DataFrame) -> int:
        period = 20
        high = df["high"]
        low = df["low"]
        close = df["close"]
        volume = df["volume"]
        if self.use_filtered_volume:
            volume = filtered_volume(volume, self.volume_ema_span)

        # Money Flow Multiplier
        mfm = ((close - low) - (high - close)) / (high - low).replace(0, np.nan)
        mfm = mfm.fillna(0)

        # Money Flow Volume
        mfv = mfm * volume

        cmf = mfv.rolling(period).sum() / volume.rolling(period).sum()
        last = cmf.iloc[-1]

        if pd.isna(last):
            return 0
        if last > 0.05:
            return 1  # buying pressure
        if last < -0.05:
            return -1  # selling pressure
        return 0


class VWAPDistance(BaseIndicator):
    """Price distance from rolling VWAP (20-day approximation)."""

    name = "vwap_distance"
    category = "volume"
    warmup_bars = 20

    def __init__(self, use_filtered_volume: bool = False, volume_ema_span: int = 5):
        self.use_filtered_volume = use_filtered_volume
        self.volume_ema_span = volume_ema_span

    def compute(self, df: pd.DataFrame) -> int:
        period = 20
        tp = (df["high"] + df["low"] + df["close"]) / 3
        volume = df["volume"]
        if self.use_filtered_volume:
            volume = filtered_volume(volume, self.volume_ema_span)

        # Rolling VWAP approximation
        vwap = (tp * volume).rolling(period).sum() / volume.rolling(period).sum()

        # ATR for distance threshold
        tr = pd.concat([
            df["high"] - df["low"],
            (df["high"] - df["close"].shift(1)).abs(),
            (df["low"] - df["close"].shift(1)).abs(),
        ], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()

        last_close = df["close"].iloc[-1]
        last_vwap = vwap.iloc[-1]
        last_atr = atr.iloc[-1]

        if pd.isna(last_vwap) or pd.isna(last_atr) or last_atr == 0:
            return 0

        if last_close > last_vwap + last_atr:
            return 1  # strong above VWAP
        if last_close < last_vwap - last_atr:
            return -1  # weak below VWAP
        return 0


class VolumeSMARatio(BaseIndicator):
    """Volume spike + price direction."""

    name = "volume_sma_ratio"
    category = "volume"
    warmup_bars = 20

    def __init__(self, use_filtered_volume: bool = False, volume_ema_span: int = 5):
        self.use_filtered_volume = use_filtered_volume
        self.volume_ema_span = volume_ema_span

    def compute(self, df: pd.DataFrame) -> int:
        period = 20
        volume = df["volume"]
        if self.use_filtered_volume:
            volume = filtered_volume(volume, self.volume_ema_span)
        close = df["close"]

        vol_sma = volume.rolling(period).mean()
        ratio = volume.iloc[-1] / vol_sma.iloc[-1] if vol_sma.iloc[-1] > 0 else 0

        if ratio > 1.5:
            # High volume day — direction matters
            if close.iloc[-1] > close.iloc[-2]:
                return 1  # high volume + up = bullish
            if close.iloc[-1] < close.iloc[-2]:
                return -1  # high volume + down = bearish
        return 0
