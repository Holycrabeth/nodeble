# -*- coding: utf-8 -*-
"""Base class for all voting indicators."""

from abc import ABC, abstractmethod

import pandas as pd


class BaseIndicator(ABC):
    """Abstract indicator that casts a +1 / 0 / -1 vote."""

    name: str = ""
    category: str = ""  # "trend" | "momentum" | "volatility" | "volume"
    warmup_bars: int = 0

    @abstractmethod
    def compute(self, df: pd.DataFrame) -> int:
        """Compute indicator on OHLCV DataFrame.

        Args:
            df: DataFrame with columns [open, high, low, close, volume]
                and a DatetimeIndex, sorted ascending. Must have at least
                `warmup_bars` rows.

        Returns:
            +1 (bullish), 0 (neutral), -1 (bearish)
        """
        raise NotImplementedError
