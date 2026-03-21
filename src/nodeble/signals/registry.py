# -*- coding: utf-8 -*-
"""Registry of all implemented indicators."""

import yaml

from nodeble.signals.trend import SMACross, EMACross, ADXTrend, Supertrend, AroonOscillator
from nodeble.signals.momentum import RSI, MACDHistogram, StochasticOscillator, CCI, WilliamsR
from nodeble.signals.volatility import (
    BollingerBandPosition, KeltnerChannel, ATRTrend, DonchianChannel, BollingerBandWidth,
)
from nodeble.signals.volume import OBVTrend, MFI, CMF, VWAPDistance, VolumeSMARatio


ALL_INDICATORS = [
    # Trend (5)
    SMACross(),
    EMACross(),
    ADXTrend(),
    Supertrend(),
    AroonOscillator(),
    # Momentum (5)
    RSI(),
    MACDHistogram(),
    StochasticOscillator(),
    CCI(),
    WilliamsR(),
    # Volatility (5)
    BollingerBandPosition(),
    KeltnerChannel(),
    ATRTrend(),
    DonchianChannel(),
    BollingerBandWidth(),
    # Volume (5)
    OBVTrend(),
    MFI(),
    CMF(),
    VWAPDistance(),
    VolumeSMARatio(),
]


def _load_indicator_evolution(config_path: str) -> dict:
    """Load indicator_evolution section from a voting config YAML."""
    try:
        with open(config_path, "r") as f:
            raw = yaml.safe_load(f)
        return raw.get("indicator_evolution", {})
    except (FileNotFoundError, TypeError):
        return {}


def _build_rsi(evo_cfg: dict) -> RSI:
    """Build RSI indicator, adaptive if configured."""
    cfg = evo_cfg.get("adaptive_rsi", {})
    if cfg.get("enabled", False):
        return RSI(
            adaptive=True,
            lookback=cfg.get("lookback", 252),
            pctile_low=cfg.get("pctile_low", 10.0),
            pctile_high=cfg.get("pctile_high", 90.0),
            floor_low=cfg.get("floor_low", 20.0),
            ceil_high=cfg.get("ceil_high", 80.0),
        )
    return RSI()


def _build_cci(evo_cfg: dict) -> CCI:
    """Build CCI indicator, adaptive if configured."""
    cfg = evo_cfg.get("adaptive_cci", {})
    if cfg.get("enabled", False):
        return CCI(
            adaptive=True,
            lookback=cfg.get("lookback", 252),
            pctile_low=cfg.get("pctile_low", 10.0),
            pctile_high=cfg.get("pctile_high", 90.0),
            floor_low=cfg.get("floor_low", -150.0),
            ceil_high=cfg.get("ceil_high", 150.0),
        )
    return CCI()


def _build_stochastic(evo_cfg: dict) -> StochasticOscillator:
    """Build StochasticOscillator, adaptive if configured."""
    cfg = evo_cfg.get("adaptive_stochastic", {})
    if cfg.get("enabled", False):
        return StochasticOscillator(
            adaptive=True,
            lookback=cfg.get("lookback", 252),
            pctile_low=cfg.get("pctile_low", 10.0),
            pctile_high=cfg.get("pctile_high", 90.0),
            floor_low=cfg.get("floor_low", 15.0),
            ceil_high=cfg.get("ceil_high", 85.0),
        )
    return StochasticOscillator()


def _build_williams_r(evo_cfg: dict) -> WilliamsR:
    """Build WilliamsR, adaptive if configured."""
    cfg = evo_cfg.get("adaptive_williams_r", {})
    if cfg.get("enabled", False):
        return WilliamsR(
            adaptive=True,
            lookback=cfg.get("lookback", 252),
            pctile_low=cfg.get("pctile_low", 10.0),
            pctile_high=cfg.get("pctile_high", 90.0),
            floor_low=cfg.get("floor_low", -85.0),
            ceil_high=cfg.get("ceil_high", -15.0),
        )
    return WilliamsR()


def _build_adx(evo_cfg: dict) -> ADXTrend:
    """Build ADXTrend, adaptive if configured."""
    cfg = evo_cfg.get("adaptive_adx", {})
    if cfg.get("enabled", False):
        return ADXTrend(
            adaptive=True,
            lookback=cfg.get("lookback", 252),
            pctile_high=cfg.get("pctile_high", 75.0),
            floor_high=cfg.get("floor_high", 20.0),
        )
    return ADXTrend()


def _build_mfi(evo_cfg: dict) -> MFI:
    """Build MFI indicator, merging volume filter + adaptive kwargs."""
    vol_cfg = evo_cfg.get("volume_noise_filter", {})
    vol_enabled = vol_cfg.get("enabled", False)
    vol_span = vol_cfg.get("ema_span", 5)

    ada_cfg = evo_cfg.get("adaptive_mfi", {})
    if ada_cfg.get("enabled", False):
        return MFI(
            use_filtered_volume=vol_enabled,
            volume_ema_span=vol_span,
            adaptive=True,
            lookback=ada_cfg.get("lookback", 252),
            pctile_low=ada_cfg.get("pctile_low", 10.0),
            pctile_high=ada_cfg.get("pctile_high", 90.0),
            floor_low=ada_cfg.get("floor_low", 15.0),
            ceil_high=ada_cfg.get("ceil_high", 85.0),
        )
    return MFI(use_filtered_volume=vol_enabled, volume_ema_span=vol_span)


def _build_crossover_indicators(evo_cfg: dict) -> list:
    """Build crossover + threshold indicators with optional confirmation bars."""
    cfg = evo_cfg.get("breakout_confirmation", {})
    bars = cfg.get("bars", 0) if cfg.get("enabled", False) else 0
    return [
        SMACross(confirmation_bars=bars),
        EMACross(confirmation_bars=bars),
        Supertrend(confirmation_bars=bars),
        AroonOscillator(confirmation_bars=bars),
        DonchianChannel(confirmation_bars=bars),
    ]


def _build_volume_indicators(evo_cfg: dict) -> list:
    """Build volume indicators with optional noise filtering + adaptive MFI."""
    cfg = evo_cfg.get("volume_noise_filter", {})
    enabled = cfg.get("enabled", False)
    ema_span = cfg.get("ema_span", 5)
    return [
        OBVTrend(use_filtered_volume=enabled, volume_ema_span=ema_span),
        _build_mfi(evo_cfg),
        CMF(use_filtered_volume=enabled, volume_ema_span=ema_span),
        VWAPDistance(use_filtered_volume=enabled, volume_ema_span=ema_span),
        VolumeSMARatio(use_filtered_volume=enabled, volume_ema_span=ema_span),
    ]


def get_all_indicators(config_path: str = None):
    """Return list of all 20 indicator instances.

    If config_path is provided, reads indicator_evolution section to
    configure adaptive RSI, breakout confirmation, and volume filtering.
    Without config_path, returns exact default behavior.
    """
    if config_path is None:
        return list(ALL_INDICATORS)

    evo_cfg = _load_indicator_evolution(config_path)

    # Trend (5): 4 crossover + adaptive ADXTrend
    crossovers = _build_crossover_indicators(evo_cfg)
    # crossovers = [SMACross, EMACross, Supertrend, AroonOscillator, DonchianChannel]
    # We need: SMACross, EMACross, ADXTrend, Supertrend, AroonOscillator as trend
    # DonchianChannel goes to volatility
    trend = [crossovers[0], crossovers[1], _build_adx(evo_cfg), crossovers[2], crossovers[3]]
    donchian = crossovers[4]

    # Momentum (5): adaptive RSI, Stochastic, CCI, WilliamsR + MACD
    momentum = [
        _build_rsi(evo_cfg),
        MACDHistogram(),
        _build_stochastic(evo_cfg),
        _build_cci(evo_cfg),
        _build_williams_r(evo_cfg),
    ]

    # Volatility (5): BB, Keltner, ATR, Donchian (from crossover builder), BBWidth
    volatility = [
        BollingerBandPosition(),
        KeltnerChannel(),
        ATRTrend(),
        donchian,
        BollingerBandWidth(),
    ]

    # Volume (5)
    volume = _build_volume_indicators(evo_cfg)

    return trend + momentum + volatility + volume


def get_indicators_by_category(category: str):
    """Return indicators filtered by category."""
    return [i for i in ALL_INDICATORS if i.category == category]


def get_max_warmup() -> int:
    """Return the maximum warmup_bars across all indicators."""
    return max(i.warmup_bars for i in ALL_INDICATORS)
