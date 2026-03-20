# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch
from datetime import date

from nodeble.strategy.factory import (
    scan_for_condors,
    load_strategy_config,
    _build_condor_config,
    _build_call_config,
)
from nodeble.core.state import SpreadState, SpreadPosition
from mock_broker import MockBroker

# Freeze today so DTE calculations stay within [21, 45] range for "2026-03-20"
_FROZEN_TODAY = date(2026, 2, 20)


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


# ──────────────────────────────────────────────────────────────────
# Ported from reference/tiger-trading/tests/test_condor_factory.py
# ──────────────────────────────────────────────────────────────────


def _make_ref_strategy_cfg(**overrides):
    """Minimal condor strategy config matching reference tests."""
    cfg = {
        "watchlist": ["SPY", "QQQ"],
        "mode": "dry_run",
        "selection": {
            "put_delta_min": 0.10,
            "put_delta_max": 0.20,
            "call_delta_min": 0.10,
            "call_delta_max": 0.20,
            "dte_min": 21,
            "dte_max": 45,
            "dte_ideal": 30,
            "prefer_monthly": True,
            "min_iv_rank": 0.35,
            "min_iv_rv_ratio": 0,
            "min_open_interest": 100,
            "max_spread_pct": 0.10,
            "min_credit_pct": 0.25,
            "earnings_blackout_days": 7,
            "cooldown_days": 0,
            "max_new_positions_per_run": 0,
            "price_guard_pct": 0.03,
        },
        "management": {
            "max_risk_per_trade": 500,
        },
        "sizing": {"spread_width_rules": [
            {"max_price": 200, "width": 5},
            {"max_price": 600, "width": 10},
            {"max_price": 999999, "width": 15},
        ]},
    }
    cfg.update(overrides)
    return cfg


def _make_ref_risk_cfg(**overrides):
    """Minimal condor risk config (FLAT dict, no 'risk' wrapper)."""
    cfg = {
        "kill_switch": False,
        "min_cash_floor": 20000,
        "max_concurrent_spreads": 8,
        "max_spreads_per_symbol": 1,
        "max_daily_orders": 16,
        "max_daily_loss": 2000,
        "max_total_exposure": 8000,
        "max_portfolio_delta": 150,
    }
    cfg.update(overrides)
    return cfg


def _make_iv_analysis(symbol, rank):
    a = MagicMock(symbol=symbol)
    a.iv_metric.rank = rank
    return a


def _make_option(put_call, strike, delta, bid, ask, oi=500, identifier=None):
    if identifier is None:
        pc_char = "P" if put_call.upper() in ("PUT", "P") else "C"
        identifier = f"{pc_char}{strike:.0f}"
    return {
        "put_call": put_call,
        "strike": strike,
        "delta": delta,
        "bid_price": bid,
        "ask_price": ask,
        "open_interest": oi,
        "identifier": identifier,
    }


class TestBuildConfigs:
    def test_build_condor_config_uses_put_deltas(self):
        cfg = _make_ref_strategy_cfg()
        result = _build_condor_config(cfg)
        assert result["selection"]["delta_range"] == [0.10, 0.20]

    def test_build_call_config_uses_call_deltas(self):
        cfg = _make_ref_strategy_cfg()
        cfg["selection"]["call_delta_min"] = 0.12
        cfg["selection"]["call_delta_max"] = 0.18
        result = _build_call_config(cfg)
        assert result["selection"]["delta_range"] == [0.12, 0.18]

    def test_build_config_carries_max_risk(self):
        cfg = _make_ref_strategy_cfg()
        cfg["management"]["max_risk_per_trade"] = 750
        result = _build_condor_config(cfg)
        assert result["selection"]["max_risk_per_trade"] == 750


class TestScanForCondors:
    def test_empty_watchlist(self):
        broker = MagicMock()
        state = SpreadState()
        cfg = _make_ref_strategy_cfg(watchlist=[])
        candidates, rejections = scan_for_condors(broker, state, _make_ref_risk_cfg(), cfg)
        assert candidates == []
        assert rejections == []

    def test_all_symbols_below_iv_threshold(self):
        broker = MagicMock()
        broker.get_option_analysis.return_value = [
            _make_iv_analysis("SPY", 0.20),
            _make_iv_analysis("QQQ", 0.25),
        ]
        state = SpreadState()
        cfg = _make_ref_strategy_cfg()
        candidates, rejections = scan_for_condors(broker, state, _make_ref_risk_cfg(), cfg)
        assert candidates == []
        assert len(rejections) == 2
        assert all("IV rank" in r["reason"] for r in rejections)

    def test_no_iv_data_rejected(self):
        broker = MagicMock()
        a = MagicMock(symbol="SPY")
        a.iv_metric = None
        broker.get_option_analysis.return_value = [a]
        state = SpreadState()
        cfg = _make_ref_strategy_cfg(watchlist=["SPY"])
        candidates, rejections = scan_for_condors(broker, state, _make_ref_risk_cfg(), cfg)
        assert candidates == []
        assert len(rejections) == 1
        assert "no IV rank" in rejections[0]["reason"]

    def test_iv_analysis_api_error(self):
        broker = MagicMock()
        broker.get_option_analysis.side_effect = Exception("API down")
        state = SpreadState()
        cfg = _make_ref_strategy_cfg(watchlist=["SPY"])
        candidates, rejections = scan_for_condors(broker, state, _make_ref_risk_cfg(), cfg)
        assert candidates == []
        assert len(rejections) == 1

    @patch("nodeble.strategy.factory.is_earnings_blackout", return_value=True)
    def test_earnings_blackout_blocks(self, mock_eb):
        broker = MagicMock()
        broker.get_option_analysis.return_value = [_make_iv_analysis("SPY", 0.50)]
        state = SpreadState()
        cfg = _make_ref_strategy_cfg(watchlist=["SPY"])
        candidates, rejections = scan_for_condors(broker, state, _make_ref_risk_cfg(), cfg)
        assert candidates == []
        assert any("earnings blackout" in r["reason"] for r in rejections)

    def test_symbol_limit_reached(self):
        broker = MagicMock()
        broker.get_option_analysis.return_value = [_make_iv_analysis("SPY", 0.50)]
        state = SpreadState()
        state.positions["SPY_ic_1"] = SpreadPosition(
            spread_id="SPY_ic_1", underlying="SPY", expiry="2026-04-01",
            spread_type="iron_condor", status="open",
        )
        cfg = _make_ref_strategy_cfg(watchlist=["SPY"])
        risk_cfg = _make_ref_risk_cfg(max_spreads_per_symbol=1)
        candidates, rejections = scan_for_condors(broker, state, risk_cfg, cfg)
        assert candidates == []
        assert any("symbol limit" in r["reason"] for r in rejections)

    @patch("nodeble.strategy.factory.is_earnings_blackout", return_value=False)
    def test_no_valid_expiry(self, mock_eb):
        broker = MagicMock()
        broker.get_option_analysis.return_value = [_make_iv_analysis("SPY", 0.50)]
        broker.get_option_expirations.return_value = [
            {"date": "2026-12-01", "period_tag": "monthly"},
        ]
        state = SpreadState()
        cfg = _make_ref_strategy_cfg(watchlist=["SPY"])
        candidates, rejections = scan_for_condors(broker, state, _make_ref_risk_cfg(), cfg)
        assert candidates == []
        assert any("no valid expiry" in r["reason"] for r in rejections)

    @patch("nodeble.strategy.factory.date", wraps=date)
    @patch("nodeble.strategy.factory.is_earnings_blackout", return_value=False)
    def test_no_stock_price(self, mock_eb, mock_date):
        mock_date.today.return_value = _FROZEN_TODAY
        broker = MagicMock()
        broker.get_option_analysis.return_value = [_make_iv_analysis("SPY", 0.50)]
        broker.get_option_expirations.return_value = [
            {"date": "2026-03-20", "period_tag": "monthly"},
        ]
        broker.get_stock_price.return_value = 0
        state = SpreadState()
        cfg = _make_ref_strategy_cfg(watchlist=["SPY"])
        candidates, rejections = scan_for_condors(broker, state, _make_ref_risk_cfg(), cfg)
        assert candidates == []
        assert any("no stock price" in r["reason"] for r in rejections)

    @patch("nodeble.strategy.factory.date", wraps=date)
    @patch("nodeble.strategy.factory.is_earnings_blackout", return_value=False)
    def test_put_side_fails_rejects_whole_condor(self, mock_eb, mock_date):
        """If put side has no viable strikes, condor is rejected (no single-side fallback)."""
        mock_date.today.return_value = _FROZEN_TODAY
        broker = MagicMock()
        broker.get_option_analysis.return_value = [_make_iv_analysis("SPY", 0.50)]
        broker.get_option_expirations.return_value = [
            {"date": "2026-03-20", "period_tag": "monthly"},
        ]
        broker.get_stock_price.return_value = 540.0
        broker.get_option_chain.side_effect = [
            [],  # put chain empty
            [_make_option("CALL", 560, 0.15, 2.0, 2.20),
             _make_option("CALL", 570, 0.05, 0.50, 0.65)],
        ]
        state = SpreadState()
        cfg = _make_ref_strategy_cfg(watchlist=["SPY"])
        candidates, rejections = scan_for_condors(broker, state, _make_ref_risk_cfg(), cfg)
        assert candidates == []
        assert any("both sides" in r["reason"] and "put" in r["reason"] for r in rejections)

    @patch("nodeble.strategy.factory.date", wraps=date)
    @patch("nodeble.strategy.factory.is_earnings_blackout", return_value=False)
    def test_call_side_fails_rejects_whole_condor(self, mock_eb, mock_date):
        """If call side has no viable strikes, condor is rejected."""
        mock_date.today.return_value = _FROZEN_TODAY
        broker = MagicMock()
        broker.get_option_analysis.return_value = [_make_iv_analysis("SPY", 0.50)]
        broker.get_option_expirations.return_value = [
            {"date": "2026-03-20", "period_tag": "monthly"},
        ]
        broker.get_stock_price.return_value = 540.0
        broker.get_option_chain.side_effect = [
            [_make_option("PUT", 520, -0.15, 3.0, 3.20),
             _make_option("PUT", 510, -0.05, 0.80, 1.00)],
            [],  # call chain empty
        ]
        state = SpreadState()
        cfg = _make_ref_strategy_cfg(watchlist=["SPY"])
        candidates, rejections = scan_for_condors(broker, state, _make_ref_risk_cfg(), cfg)
        assert candidates == []
        assert any("both sides" in r["reason"] and "call" in r["reason"] for r in rejections)

    @patch("nodeble.strategy.factory.date", wraps=date)
    @patch("nodeble.strategy.factory.is_earnings_blackout", return_value=False)
    def test_happy_path_iron_condor(self, mock_eb, mock_date):
        """Full happy path: IV passes, both sides qualify, candidate built."""
        mock_date.today.return_value = _FROZEN_TODAY
        broker = MagicMock()
        broker.get_option_analysis.return_value = [_make_iv_analysis("SPY", 0.50)]
        broker.get_option_expirations.return_value = [
            {"date": "2026-03-20", "period_tag": "monthly"},
        ]
        broker.get_stock_price.return_value = 540.0

        put_chain = [
            _make_option("PUT", 520, -0.15, 3.50, 3.70, identifier="SPY260320P520"),
            _make_option("PUT", 510, -0.05, 0.80, 1.00, identifier="SPY260320P510"),
        ]
        call_chain = [
            _make_option("CALL", 560, 0.15, 3.50, 3.70, identifier="SPY260320C560"),
            _make_option("CALL", 570, 0.05, 0.80, 1.00, identifier="SPY260320C570"),
        ]
        broker.get_option_chain.side_effect = [put_chain, call_chain]

        state = SpreadState()
        cfg = _make_ref_strategy_cfg(watchlist=["SPY"])
        candidates, rejections = scan_for_condors(broker, state, _make_ref_risk_cfg(), cfg)

        assert len(candidates) == 1
        c = candidates[0]
        assert c.underlying == "SPY"
        assert c.spread_type == "iron_condor"
        assert c.expiry == "2026-03-20"
        assert c.iv_rank == 0.50
        assert c.total_credit > 0
        assert c.max_risk > 0
        assert c.credit_risk_ratio > 0

    @patch("nodeble.strategy.factory.date", wraps=date)
    @patch("nodeble.strategy.factory.is_earnings_blackout", return_value=False)
    def test_sorted_by_credit_risk_ratio(self, mock_eb, mock_date):
        """Multiple candidates should be sorted by credit/risk ratio (best first)."""
        mock_date.today.return_value = _FROZEN_TODAY
        broker = MagicMock()
        broker.get_option_analysis.return_value = [
            _make_iv_analysis("SPY", 0.50),
            _make_iv_analysis("QQQ", 0.60),
        ]
        broker.get_option_expirations.return_value = [
            {"date": "2026-03-20", "period_tag": "monthly"},
        ]

        broker.get_stock_price.side_effect = [540.0, 460.0]

        spy_puts = [
            _make_option("PUT", 520, -0.15, 2.00, 2.20),
            _make_option("PUT", 510, -0.05, 0.50, 0.70),
        ]
        spy_calls = [
            _make_option("CALL", 560, 0.15, 2.00, 2.20),
            _make_option("CALL", 570, 0.05, 0.50, 0.70),
        ]
        qqq_puts = [
            _make_option("PUT", 440, -0.15, 4.00, 4.20),
            _make_option("PUT", 430, -0.05, 0.80, 1.00),
        ]
        qqq_calls = [
            _make_option("CALL", 480, 0.15, 4.00, 4.20),
            _make_option("CALL", 490, 0.05, 0.80, 1.00),
        ]
        broker.get_option_chain.side_effect = [spy_puts, spy_calls, qqq_puts, qqq_calls]

        state = SpreadState()
        cfg = _make_ref_strategy_cfg()
        candidates, _ = scan_for_condors(broker, state, _make_ref_risk_cfg(), cfg)

        if len(candidates) >= 2:
            assert candidates[0].credit_risk_ratio >= candidates[1].credit_risk_ratio

    @patch("nodeble.strategy.factory.date", wraps=date)
    @patch("nodeble.strategy.factory.is_earnings_blackout", return_value=False)
    def test_credit_below_min_rejected(self, mock_eb, mock_date):
        """Candidate with credit below min_credit_pct is rejected."""
        mock_date.today.return_value = _FROZEN_TODAY
        broker = MagicMock()
        broker.get_option_analysis.return_value = [_make_iv_analysis("SPY", 0.50)]
        broker.get_option_expirations.return_value = [
            {"date": "2026-03-20", "period_tag": "monthly"},
        ]
        broker.get_stock_price.return_value = 540.0

        put_chain = [
            _make_option("PUT", 520, -0.15, 0.30, 0.40),
            _make_option("PUT", 510, -0.05, 0.20, 0.25),
        ]
        call_chain = [
            _make_option("CALL", 560, 0.15, 0.30, 0.40),
            _make_option("CALL", 570, 0.05, 0.20, 0.25),
        ]
        broker.get_option_chain.side_effect = [put_chain, call_chain]

        state = SpreadState()
        cfg = _make_ref_strategy_cfg(watchlist=["SPY"])
        candidates, rejections = scan_for_condors(broker, state, _make_ref_risk_cfg(), cfg)
        assert candidates == [] or any("credit" in r.get("reason", "") for r in rejections)

    @patch("nodeble.strategy.factory.is_earnings_blackout", return_value=False)
    def test_expirations_api_error(self, mock_eb):
        broker = MagicMock()
        broker.get_option_analysis.return_value = [_make_iv_analysis("SPY", 0.50)]
        broker.get_option_expirations.side_effect = Exception("API error")
        state = SpreadState()
        cfg = _make_ref_strategy_cfg(watchlist=["SPY"])
        candidates, rejections = scan_for_condors(broker, state, _make_ref_risk_cfg(), cfg)
        assert candidates == []
        assert any("expirations" in r["reason"] for r in rejections)

    def test_all_spread_type_is_iron_condor(self):
        """All rejections and candidates should have spread_type=iron_condor."""
        broker = MagicMock()
        broker.get_option_analysis.return_value = [
            _make_iv_analysis("SPY", 0.20),
        ]
        state = SpreadState()
        cfg = _make_ref_strategy_cfg(watchlist=["SPY"])
        _, rejections = scan_for_condors(broker, state, _make_ref_risk_cfg(), cfg)
        for r in rejections:
            assert r["spread_type"] == "iron_condor"


class TestLoadStrategyConfig:
    def test_loads_yaml(self, tmp_path):
        f = tmp_path / "strategy.yaml"
        f.write_text("watchlist:\n  - SPY\nselection:\n  min_iv_rank: 0.40\n")
        cfg = load_strategy_config(str(f))
        assert cfg["watchlist"] == ["SPY"]
        assert cfg["selection"]["min_iv_rank"] == 0.40
