"""End-to-end integration test: scan + manage cycle with MockBroker."""
from nodeble.core.state import SpreadState
from nodeble.core import risk as options_risk
from nodeble.strategy.factory import scan_for_condors
from nodeble.strategy.manager import evaluate_positions
from mock_broker import MockBroker


def _make_cfgs():
    strategy_cfg = {
        "mode": "dry_run",
        "watchlist": ["SPY"],
        "selection": {
            "min_iv_rank": 0.30, "min_iv_rv_ratio": 0,
            "put_delta_min": 0.10, "put_delta_max": 0.20,
            "call_delta_min": 0.10, "call_delta_max": 0.20,
            "min_open_interest": 100, "max_spread_pct": 0.10,
            "min_credit_pct": 0.20, "dte_min": 21, "dte_max": 45,
            "dte_ideal": 30, "prefer_monthly": True,
            "earnings_blackout_days": 7, "cooldown_days": 0,
            "max_new_positions_per_run": 0, "price_guard_pct": 0.03,
            "delta_range": [0.10, 0.20],
            "max_risk_per_trade": 3500,
        },
        "management": {
            "max_risk_per_trade": 3500,
            "profit_take_pct": 0.50,
            "stop_loss_pct": 2.0,
            "close_before_dte": 1,
        },
        "execution": {"fill_timeout_sec": 1, "allow_degradation": False},
        "sizing": {"spread_width_rules": [
            {"max_price": 200, "width": 5},
            {"max_price": 500, "width": 10},
            {"max_price": 999999, "width": 15},
        ]},
    }
    risk_cfg = {
        "kill_switch": False, "min_cash_floor": 20000,
        "max_concurrent_spreads": 10, "max_spreads_per_symbol": 2,
        "max_daily_orders": 16, "max_daily_loss": 1500,
        "max_total_exposure": 20000, "max_portfolio_delta": 200,
    }
    return strategy_cfg, risk_cfg


def test_full_scan_cycle_dry_run():
    broker = MockBroker()
    state = SpreadState()
    strategy_cfg, risk_cfg = _make_cfgs()

    candidates, rejections = scan_for_condors(
        broker=broker, state=state,
        risk_cfg=risk_cfg, strategy_cfg=strategy_cfg,
        dry_run=True,
    )
    assert isinstance(candidates, list)
    assert isinstance(rejections, list)


def test_manage_cycle_no_positions():
    broker = MockBroker()
    state = SpreadState()
    strategy_cfg, risk_cfg = _make_cfgs()

    actions = evaluate_positions(
        state=state, broker=broker,
        strategy_cfg=strategy_cfg,
    )
    assert actions == []


def test_state_roundtrip(tmp_path):
    state_path = str(tmp_path / "state.json")
    state = SpreadState()
    state.last_scan_date = "2026-03-20"
    state.save(state_path)

    loaded = SpreadState.load(state_path)
    assert loaded.last_scan_date == "2026-03-20"
    assert len(loaded.positions) == 0
