from unittest.mock import MagicMock

from nodeble.strategy.factory import scan_for_condors
from nodeble.core.state import SpreadState
from mock_broker import MockBroker


def _make_strategy_cfg():
    return {
        "watchlist": ["SPY"],
        "selection": {
            "min_iv_rank": 0.30,
            "min_iv_rv_ratio": 0,
            "put_delta_min": 0.10,
            "put_delta_max": 0.20,
            "call_delta_min": 0.10,
            "call_delta_max": 0.20,
            "min_open_interest": 100,
            "max_spread_pct": 0.10,
            "min_credit_pct": 0.20,
            "dte_min": 21,
            "dte_max": 45,
            "dte_ideal": 30,
            "prefer_monthly": True,
            "earnings_blackout_days": 7,
            "cooldown_days": 0,
            "max_new_positions_per_run": 0,
            "price_guard_pct": 0.03,
        },
        "management": {"max_risk_per_trade": 3500},
        "sizing": {"spread_width_rules": [
            {"max_price": 200, "width": 5},
            {"max_price": 500, "width": 10},
            {"max_price": 999999, "width": 15},
        ]},
    }


def _make_risk_cfg():
    """Risk config is a FLAT dict."""
    return {
        "kill_switch": False,
        "max_concurrent_spreads": 10,
        "max_spreads_per_symbol": 2,
    }


def test_scan_empty_watchlist():
    broker = MockBroker()
    state = SpreadState()
    cfg = _make_strategy_cfg()
    cfg["watchlist"] = []
    candidates, rejections = scan_for_condors(
        broker=broker, state=state, risk_cfg=_make_risk_cfg(),
        strategy_cfg=cfg, dry_run=True,
    )
    assert candidates == []


def test_scan_rejects_low_iv():
    broker = MockBroker()
    mock_analysis = MagicMock()
    mock_analysis.symbol = "SPY"
    mock_iv = MagicMock()
    mock_iv.rank = 0.10
    mock_analysis.iv_metric = mock_iv
    broker._option_analyses = [mock_analysis]

    state = SpreadState()
    candidates, rejections = scan_for_condors(
        broker=broker, state=state, risk_cfg=_make_risk_cfg(),
        strategy_cfg=_make_strategy_cfg(), dry_run=True,
    )
    assert candidates == []
    assert len(rejections) > 0
