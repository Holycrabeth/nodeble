from nodeble.strategy.adaptive import compute_adaptive_params

# Default adaptive config matching strategy.yaml.example
ADAPTIVE_CFG = {
    "vix_tiers": [
        {"max_vix": 15, "delta_scale": 1.50, "dte_min": 15, "dte_max": 30},
        {"max_vix": 20, "delta_scale": 1.00, "dte_min": 12, "dte_max": 25},
        {"max_vix": 25, "delta_scale": 0.85, "dte_min": 7, "dte_max": 20},
        {"max_vix": 999, "delta_scale": 0.70, "dte_min": 3, "dte_max": 15},
    ],
    "skew": {
        "neutral_zone": [0.45, 0.55],
        "max_skew_ratio": 0.25,
    },
}

# Base selection config (from strategy.yaml)
BASE_CFG = {
    "put_delta_min": 0.08,
    "put_delta_max": 0.15,
    "call_delta_min": 0.08,
    "call_delta_max": 0.15,
    "dte_min": 30,
    "dte_max": 45,
    "dte_ideal": 35,
}


def test_vix_calm_scales_up():
    """VIX <= 15 -> delta_scale 1.50, DTE 15-30."""
    result = compute_adaptive_params(
        bull_share=0.50, vix=12.0, base_config=BASE_CFG, adaptive_config=ADAPTIVE_CFG,
    )
    # Base put_delta_max 0.15 * 1.50 = 0.225
    assert abs(result["put_delta_max"] - 0.225) < 0.001
    assert abs(result["call_delta_max"] - 0.225) < 0.001
    assert result["dte_min"] == 15
    assert result["dte_max"] == 30
    assert result["dte_ideal"] == 22  # midpoint of 15-30


def test_vix_high_scales_down():
    """VIX 25+ -> delta_scale 0.70, DTE 3-15."""
    result = compute_adaptive_params(
        bull_share=0.50, vix=30.0, base_config=BASE_CFG, adaptive_config=ADAPTIVE_CFG,
    )
    # Base put_delta_max 0.15 * 0.70 = 0.105
    assert abs(result["put_delta_max"] - 0.105) < 0.001
    assert result["dte_min"] == 3
    assert result["dte_max"] == 15
    assert result["dte_ideal"] == 9  # midpoint of 3-15


def test_vix_unavailable_falls_to_middle():
    """VIX None -> use 15-20 tier (delta_scale 1.00)."""
    result = compute_adaptive_params(
        bull_share=0.50, vix=None, base_config=BASE_CFG, adaptive_config=ADAPTIVE_CFG,
    )
    # delta_scale 1.00 -> unchanged
    assert abs(result["put_delta_max"] - 0.15) < 0.001
    assert result["dte_min"] == 12
    assert result["dte_max"] == 25


def test_neutral_symmetric():
    """bull_share 0.50 (neutral zone) -> symmetric deltas."""
    result = compute_adaptive_params(
        bull_share=0.50, vix=18.0, base_config=BASE_CFG, adaptive_config=ADAPTIVE_CFG,
    )
    assert result["put_delta_max"] == result["call_delta_max"]
    assert result["put_delta_min"] == result["call_delta_min"]


def test_bearish_skew():
    """bull_share 0.35 (bearish) -> put delta lower, call delta higher."""
    result = compute_adaptive_params(
        bull_share=0.35, vix=18.0, base_config=BASE_CFG, adaptive_config=ADAPTIVE_CFG,
    )
    # Bearish: put side dangerous -> lower delta (farther OTM)
    assert result["put_delta_max"] < result["call_delta_max"]
    assert result["put_delta_min"] < result["call_delta_min"]


def test_bullish_skew():
    """bull_share 0.70 (bullish) -> call delta lower, put delta higher."""
    result = compute_adaptive_params(
        bull_share=0.70, vix=18.0, base_config=BASE_CFG, adaptive_config=ADAPTIVE_CFG,
    )
    # Bullish: call side dangerous -> lower delta (farther OTM)
    assert result["call_delta_max"] < result["put_delta_max"]
    assert result["call_delta_min"] < result["put_delta_min"]


def test_max_skew_at_extreme():
    """bull_share 0.25 (strongly bearish, <= 0.30 clamp) -> maximum skew ratio applied."""
    result = compute_adaptive_params(
        bull_share=0.25, vix=18.0, base_config=BASE_CFG, adaptive_config=ADAPTIVE_CFG,
    )
    # bull_share <= 0.30 -> clamped to max skew (-0.25)
    # Base 0.15 * 1.00 (VIX 15-20) = 0.15
    # put_delta_max = 0.15 * (1 + (-0.25)) = 0.15 * 0.75 = 0.1125
    # call_delta_max = 0.15 * (1 - (-0.25)) = 0.15 * 1.25 = 0.1875
    assert abs(result["put_delta_max"] - 0.1125) < 0.001
    assert abs(result["call_delta_max"] - 0.1875) < 0.001


def test_combined_vix_and_skew():
    """VIX calm + strongly bearish -> scaled up AND max skewed."""
    result = compute_adaptive_params(
        bull_share=0.25, vix=12.0, base_config=BASE_CFG, adaptive_config=ADAPTIVE_CFG,
    )
    # VIX <=15: delta_scale 1.50 -> base 0.15 * 1.50 = 0.225
    # bull_share 0.25 <= 0.30 -> clamped to max skew (-0.25)
    # put_delta_max = 0.225 * 0.75 = 0.16875
    # call_delta_max = 0.225 * 1.25 = 0.28125
    assert abs(result["put_delta_max"] - 0.16875) < 0.001
    assert abs(result["call_delta_max"] - 0.28125) < 0.001
    assert result["dte_min"] == 15
    assert result["dte_max"] == 30
