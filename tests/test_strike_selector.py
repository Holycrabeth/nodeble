from nodeble.strategy.strike_selector import (
    get_spread_width,
    select_put_spread_strikes,
    select_call_spread_strikes,
    build_candidate,
    SpreadCandidate,
)


def test_spread_width_tiers():
    cfg = {"sizing": {"spread_width_rules": [
        {"max_price": 200, "width": 5},
        {"max_price": 500, "width": 10},
        {"max_price": 999999, "width": 15},
    ]}}
    assert get_spread_width(150.0, cfg) == 5
    assert get_spread_width(300.0, cfg) == 10
    assert get_spread_width(600.0, cfg) == 15


def test_spread_candidate_fields():
    c = SpreadCandidate(underlying="SPY", spread_type="iron_condor", expiry="2026-04-01", dte=30)
    assert c.underlying == "SPY"
    assert c.total_credit == 0.0
    assert c.max_risk == 0.0
    assert c.contracts == 1
