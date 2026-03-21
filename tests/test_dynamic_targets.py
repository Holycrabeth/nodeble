from nodeble.strategy.manager import _get_dynamic_profit_target

DYNAMIC_CFG = {"management": {"dynamic_profit_targets": [
    {"max_vix": 15, "profit_take_pct": 0.40},
    {"max_vix": 20, "profit_take_pct": 0.50},
    {"max_vix": 25, "profit_take_pct": 0.60},
    {"max_vix": 999, "profit_take_pct": 0.75},
]}}


def test_vix_calm_target_40():
    assert _get_dynamic_profit_target(DYNAMIC_CFG, 12.0) == 0.40


def test_vix_standard_target_50():
    assert _get_dynamic_profit_target(DYNAMIC_CFG, 18.0) == 0.50


def test_vix_elevated_target_60():
    assert _get_dynamic_profit_target(DYNAMIC_CFG, 22.0) == 0.60


def test_vix_high_target_75():
    assert _get_dynamic_profit_target(DYNAMIC_CFG, 30.0) == 0.75


def test_vix_none_fallback_50():
    assert _get_dynamic_profit_target(DYNAMIC_CFG, None) == 0.50


def test_no_dynamic_targets_falls_to_static():
    cfg = {"management": {"profit_take_pct": 0.65}}
    assert _get_dynamic_profit_target(cfg, 18.0) == 0.65


def test_no_dynamic_targets_no_static_defaults_50():
    cfg = {"management": {}}
    assert _get_dynamic_profit_target(cfg, 18.0) == 0.50
