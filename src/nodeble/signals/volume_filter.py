# -*- coding: utf-8 -*-
"""Volume noise filtering — EMA smoothing for volume indicators."""

import pandas as pd


def filtered_volume(volume: pd.Series, ema_span: int = 5) -> pd.Series:
    """EMA-smoothed volume to reduce single-day spike noise."""
    return volume.ewm(span=ema_span, adjust=False).mean()
