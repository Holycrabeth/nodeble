from nodeble.core.state import SpreadState, SpreadPosition, SpreadLeg
from nodeble.core import risk as options_risk


def _make_risk_cfg():
    """Risk config is a FLAT dict — no 'risk' wrapper."""
    return {
        "kill_switch": False,
        "min_cash_floor": 20000,
        "max_concurrent_spreads": 10,
        "max_spreads_per_symbol": 2,
        "max_daily_orders": 16,
        "max_daily_loss": 1500,
        "max_total_exposure": 20000,
        "max_portfolio_delta": 200,
    }


def test_kill_switch_off():
    cfg = _make_risk_cfg()
    assert options_risk.check_kill_switch(cfg) is True


def test_kill_switch_on():
    cfg = _make_risk_cfg()
    cfg["kill_switch"] = True
    assert options_risk.check_kill_switch(cfg) is False


def test_max_spreads_under_limit():
    cfg = _make_risk_cfg()
    state = SpreadState()
    assert options_risk.check_max_spreads(state, cfg) is True


def test_max_spreads_at_limit():
    cfg = _make_risk_cfg()
    cfg["max_concurrent_spreads"] = 0
    state = SpreadState()
    pos = SpreadPosition(
        spread_id="test", underlying="SPY", expiry="2026-04-01",
        spread_type="iron_condor", legs=[], entry_date="2026-03-20",
        entry_credit=1.0, max_risk=4.0, contracts=1, status="open",
    )
    state.positions["test"] = pos
    assert options_risk.check_max_spreads(state, cfg) is False


def test_verify_no_naked_legs_covered():
    """A position with matching BUY/SELL legs is not naked."""
    pos = SpreadPosition(
        spread_id="test", underlying="SPY", expiry="2026-04-01",
        spread_type="bull_put", legs=[
            SpreadLeg(identifier="SPY_P250", strike=250, put_call="P",
                      action="SELL", contracts=1, entry_premium=3.0,
                      order_id=1, status="filled", entry_delta=-0.15),
            SpreadLeg(identifier="SPY_P245", strike=245, put_call="P",
                      action="BUY", contracts=1, entry_premium=1.0,
                      order_id=2, status="filled", entry_delta=-0.10),
        ],
        entry_date="2026-03-20", entry_credit=2.0, max_risk=3.0,
        contracts=1, status="open",
    )
    assert options_risk.verify_no_naked_legs(pos) is True


def test_verify_naked_leg_detected():
    """A SELL leg without a covering BUY should be detected."""
    pos = SpreadPosition(
        spread_id="test", underlying="SPY", expiry="2026-04-01",
        spread_type="bull_put", legs=[
            SpreadLeg(identifier="SPY_P250", strike=250, put_call="P",
                      action="SELL", contracts=1, entry_premium=3.0,
                      order_id=1, status="filled", entry_delta=-0.15),
        ],
        entry_date="2026-03-20", entry_credit=3.0, max_risk=2.0,
        contracts=1, status="open",
    )
    assert options_risk.verify_no_naked_legs(pos) is False


def test_load_risk_config(tmp_path):
    """Test loading risk config from YAML flattens the 'risk' wrapper."""
    cfg_path = tmp_path / "risk.yaml"
    cfg_path.write_text("risk:\n  kill_switch: true\n  min_cash_floor: 50000\n")
    cfg = options_risk.load_risk_config(str(cfg_path))
    assert cfg["kill_switch"] is True
    assert cfg["min_cash_floor"] == 50000
    # Should be flat — no 'risk' wrapper
    assert "risk" not in cfg
