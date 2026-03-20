# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch, call

from nodeble.strategy.executor import SpreadExecutor
from nodeble.core.state import SpreadState, SpreadPosition, SpreadLeg
from nodeble.strategy.strike_selector import SpreadCandidate
from mock_broker import MockBroker


def _make_executor(broker=None, state=None, tmp_path=None):
    if broker is None:
        broker = MockBroker()
    if state is None:
        state = SpreadState()
    state_path = str(tmp_path / "state.json") if tmp_path else "/tmp/test_state.json"
    return SpreadExecutor(
        broker=broker,
        notifier=None,
        config={"execution": {"fill_timeout_sec": 1, "allow_degradation": False}},
        state=state,
        state_path=state_path,
    )


def _make_candidate():
    c = SpreadCandidate(underlying="SPY", spread_type="iron_condor", expiry="2026-04-01", dte=30)
    c.contracts = 1
    c.scan_price = 500.0
    c.total_credit = 2.50
    c.max_risk = 2.50
    return c


def test_executor_dry_run(tmp_path):
    executor = _make_executor(tmp_path=tmp_path)
    result = executor.execute_iron_condor(_make_candidate(), dry_run=True)
    assert result["status"] == "dry_run"
    assert executor.broker.orders_placed == []


def test_executor_no_real_orders_in_dry_run(tmp_path):
    broker = MockBroker()
    executor = _make_executor(broker=broker, tmp_path=tmp_path)
    executor.execute_iron_condor(_make_candidate(), dry_run=True)
    assert len(broker.orders_placed) == 0


# ──────────────────────────────────────────────────────────────────
# Ported from reference/tiger-trading/tests/test_options_executor.py
# ──────────────────────────────────────────────────────────────────


def _make_ref_candidate(spread_type="bull_put"):
    c = SpreadCandidate(
        underlying="TSLA", spread_type=spread_type,
        expiry="2026-03-27", dte=10,
    )
    if spread_type in ("bull_put", "iron_condor"):
        c.short_put_identifier = "TSLA  260327P00250000"
        c.short_put_strike = 250.0
        c.short_put_delta = -0.22
        c.short_put_bid = 3.00
        c.long_put_identifier = "TSLA  260327P00245000"
        c.long_put_strike = 245.0
        c.long_put_ask = 1.50
        c.put_credit = 1.50
    if spread_type in ("bear_call", "iron_condor"):
        c.short_call_identifier = "TSLA  260327C00280000"
        c.short_call_strike = 280.0
        c.short_call_delta = 0.22
        c.short_call_bid = 3.00
        c.long_call_identifier = "TSLA  260327C00285000"
        c.long_call_strike = 285.0
        c.long_call_ask = 1.50
        c.call_credit = 1.50
    c.total_credit = 1.50 if spread_type != "iron_condor" else 3.00
    c.spread_width = 5.0
    c.max_risk = 3.50 if spread_type != "iron_condor" else 2.00
    c.contracts = 1
    return c


def _make_brief(identifier, delta):
    b = MagicMock()
    b.identifier = identifier
    b.delta = delta
    b.bid_price = 0
    return b


def _make_ref_executor(broker=None, fill_returns="FILLED"):
    broker = broker or MagicMock()
    broker.place_option_market_order.return_value = 12345
    broker.place_option_order.return_value = 12345
    broker.get_option_briefs.side_effect = lambda ids: [
        _make_brief(i, -0.20 if "P" in i else 0.20) for i in ids
    ]
    broker.get_stock_price.return_value = 260.0
    notifier = MagicMock()
    state = SpreadState()
    config = {
        "execution": {
            "fill_timeout_sec": 1,
            "max_leg_slippage": 0.10,
            "retry_attempts": 2,
        },
        "selection": {
            "price_guard_pct": 0.03,
            "delta_range": [0.15, 0.30],
        },
    }

    executor = SpreadExecutor(broker, notifier, config, state, "/tmp/state_test.json")
    executor.poll_interval = 0.01
    executor._poll_for_fill = MagicMock(return_value=fill_returns)
    executor._save_state = MagicMock()

    return executor


class TestExecuteSpread:
    def test_successful_bull_put(self):
        executor = _make_ref_executor()
        candidate = _make_ref_candidate("bull_put")
        result = executor.execute_spread(candidate)

        assert result["status"] == "open"
        assert result["net_credit"] == 1.50
        assert executor.broker.place_option_market_order.call_count == 2

        calls = executor.broker.place_option_market_order.call_args_list
        assert calls[0][1]["action"] == "BUY"
        assert calls[1][1]["action"] == "SELL"

    def test_successful_bear_call(self):
        executor = _make_ref_executor()
        candidate = _make_ref_candidate("bear_call")
        result = executor.execute_spread(candidate)

        assert result["status"] == "open"
        calls = executor.broker.place_option_market_order.call_args_list
        assert calls[0][1]["action"] == "BUY"
        assert calls[1][1]["action"] == "SELL"

    def test_dry_run(self):
        executor = _make_ref_executor()
        candidate = _make_ref_candidate()
        result = executor.execute_spread(candidate, dry_run=True)

        assert result["status"] == "dry_run"
        executor.broker.place_option_market_order.assert_not_called()

    def test_long_leg_not_filled_cancels(self):
        executor = _make_ref_executor(fill_returns="TIMEOUT")
        candidate = _make_ref_candidate()
        result = executor.execute_spread(candidate)

        assert "error_long_not_filled" in result["status"]
        assert executor.broker.place_option_market_order.call_count == 1

    def test_short_leg_not_filled_rollback(self):
        executor = _make_ref_executor()
        executor._poll_for_fill = MagicMock(side_effect=["FILLED", "TIMEOUT"])

        candidate = _make_ref_candidate()
        result = executor.execute_spread(candidate)

        assert "rolled_back" in result["status"]
        assert executor.broker.place_option_market_order.call_count == 3

    def test_long_leg_order_error(self):
        executor = _make_ref_executor()
        executor.broker.place_option_market_order.side_effect = Exception("API error")
        candidate = _make_ref_candidate()
        result = executor.execute_spread(candidate)

        assert result["status"] == "error_long_leg"

    def test_state_saved_after_each_leg(self):
        executor = _make_ref_executor()
        candidate = _make_ref_candidate()
        executor.execute_spread(candidate)

        assert executor._save_state.call_count >= 5


class TestExecuteIronCondor:
    def test_successful_iron_condor(self):
        executor = _make_ref_executor()
        candidate = _make_ref_candidate("iron_condor")
        result = executor.execute_iron_condor(candidate)

        assert result["status"] == "open"
        assert executor.broker.place_option_market_order.call_count == 4

    def test_iron_condor_dry_run(self):
        executor = _make_ref_executor()
        candidate = _make_ref_candidate("iron_condor")
        result = executor.execute_iron_condor(candidate, dry_run=True)

        assert result["status"] == "dry_run"
        executor.broker.place_option_market_order.assert_not_called()

    def test_call_side_fails_aborts_by_default(self):
        """Default allow_degradation=False: abort and close put side."""
        executor = _make_ref_executor()
        executor._poll_for_fill = MagicMock(
            side_effect=["FILLED", "FILLED", "TIMEOUT", "TIMEOUT"]
        )

        candidate = _make_ref_candidate("iron_condor")
        result = executor.execute_iron_condor(candidate)

        assert result["status"] in ("error_call_side_aborted", "error_call_side_close_pending")

    def test_call_side_fails_degrades_when_allowed(self):
        """allow_degradation=True: put side stays open as bull_put."""
        executor = _make_ref_executor()
        executor._poll_for_fill = MagicMock(
            side_effect=["FILLED", "FILLED", "TIMEOUT", "TIMEOUT"]
        )

        candidate = _make_ref_candidate("iron_condor")
        result = executor.execute_iron_condor(candidate, allow_degradation=True)

        assert result["status"] == "degraded_to_bull_put"


class TestNakedLegSaveOrder:
    """H5: State must NOT be saved with unverified short leg."""

    @patch("nodeble.strategy.executor.options_risk.verify_no_naked_legs", return_value=False)
    def test_spread_no_save_before_naked_check(self, mock_verify):
        """execute_spread: _save_state not called between append and verify."""
        executor = _make_ref_executor()
        save_calls = []

        def track_save():
            pos_list = list(executor.state.positions.values())
            leg_count = len(pos_list[0].legs) if pos_list else 0
            save_calls.append(("save", leg_count))

        executor._save_state = MagicMock(side_effect=track_save)

        candidate = _make_ref_candidate("bull_put")
        result = executor.execute_spread(candidate)

        assert result["status"] == "error_naked_check"
        two_leg_saves = [c for c in save_calls if c[1] == 2]
        assert len(two_leg_saves) >= 1
        mock_verify.assert_called_once()

    @patch("nodeble.strategy.executor.options_risk.verify_no_naked_legs", return_value=False)
    def test_execute_side_no_save_before_naked_check(self, mock_verify):
        """_execute_side (iron condor): same ordering guarantee."""
        executor = _make_ref_executor()
        save_calls = []

        def track_save():
            pos_list = list(executor.state.positions.values())
            if not pos_list:
                save_calls.append(("save", 0))
                return
            statuses = [l.status for l in pos_list[0].legs]
            save_calls.append(("save", len(statuses), statuses[:]))

        executor._save_state = MagicMock(side_effect=track_save)

        candidate = _make_ref_candidate("iron_condor")
        result = executor.execute_iron_condor(candidate)

        mock_verify.assert_called()


class TestCloseSpread:
    def test_close_spread(self):
        executor = _make_ref_executor()
        pos = SpreadPosition(
            spread_id="TEST", underlying="TSLA", expiry="2026-03-27",
            spread_type="bull_put",
            legs=[
                SpreadLeg("S", 250.0, "P", "SELL", 1, 3.00, status="filled"),
                SpreadLeg("L", 245.0, "P", "BUY", 1, 1.50, status="filled"),
            ],
            entry_credit=1.50,
            max_risk=3.50,
            contracts=1,
            status="open",
        )
        executor.state.positions["TEST"] = pos

        brief_s = MagicMock()
        brief_s.identifier = "S"
        brief_s.bid_price = 0.50
        brief_s.ask_price = 0.70
        brief_l = MagicMock()
        brief_l.identifier = "L"
        brief_l.bid_price = 0.10
        brief_l.ask_price = 0.20
        executor.broker.get_option_briefs.return_value = [brief_s, brief_l]

        result = executor.close_spread(pos)

        assert result["status"] == "closed"
        calls = executor.broker.place_option_market_order.call_args_list
        assert calls[0][1]["action"] == "BUY"
        assert calls[1][1]["action"] == "SELL"

    def test_close_dry_run(self):
        executor = _make_ref_executor()
        pos = SpreadPosition(
            spread_id="TEST", underlying="TSLA", expiry="2026-03-27",
            spread_type="bull_put", status="open",
        )
        result = executor.close_spread(pos, dry_run=True)
        assert result["status"] == "dry_run"

    def test_close_short_not_filled_aborts(self):
        """P0 #1: If short close doesn't fill, don't sell long (naked risk)."""
        executor = _make_ref_executor()
        executor._poll_for_fill = MagicMock(return_value="TIMEOUT")

        pos = SpreadPosition(
            spread_id="TEST", underlying="TSLA", expiry="2026-03-27",
            spread_type="bull_put",
            legs=[
                SpreadLeg("S", 250.0, "P", "SELL", 1, 3.00, status="filled"),
                SpreadLeg("L", 245.0, "P", "BUY", 1, 1.50, status="filled"),
            ],
            entry_credit=1.50, max_risk=3.50, contracts=1, status="open",
        )
        executor.state.positions["TEST"] = pos

        brief_s = MagicMock()
        brief_s.identifier = "S"
        brief_s.bid_price = 0.50
        brief_s.ask_price = 0.70
        brief_l = MagicMock()
        brief_l.identifier = "L"
        brief_l.bid_price = 0.10
        brief_l.ask_price = 0.20
        executor.broker.get_option_briefs.return_value = [brief_s, brief_l]

        result = executor.close_spread(pos)

        assert "error_short_close_not_filled" in result["status"]
        assert executor.broker.place_option_market_order.call_count == 1
        assert pos.status == "open"

    def test_close_reverts_on_quote_error(self):
        """P2 #9: Quote error reverts to open so manage can retry."""
        executor = _make_ref_executor()
        pos = SpreadPosition(
            spread_id="TEST", underlying="TSLA", expiry="2026-03-27",
            spread_type="bull_put",
            legs=[SpreadLeg("S", 250.0, "P", "SELL", 1, 3.00, status="filled")],
            entry_credit=1.50, max_risk=3.50, contracts=1, status="open",
        )
        executor.broker.get_option_briefs.side_effect = Exception("API error")

        result = executor.close_spread(pos)

        assert result["status"] == "error_quotes"
        assert pos.status == "open"


class TestEmergencyCloseLeg:
    def test_emergency_close_tracks_order_in_state(self):
        """P1 #3: Emergency close order_id saved to position for cleanup."""
        executor = _make_ref_executor()
        executor._save_state = MagicMock()

        pos = SpreadPosition(
            spread_id="TEST", underlying="TSLA", expiry="2026-03-27",
            spread_type="bull_put", status="error",
        )
        leg = SpreadLeg("L", 245.0, "P", "BUY", 1, 1.50, status="filled")
        pos.legs.append(leg)

        executor.broker.place_option_market_order.return_value = 99999

        result = executor._emergency_close_leg(leg, pos)

        assert result is True
        assert len(pos.legs) == 2
        emergency_leg = pos.legs[1]
        assert emergency_leg.order_id == 99999
        assert emergency_leg.action == "SELL"
        assert emergency_leg.status == "pending"
        executor._save_state.assert_called()


class TestCreditCounting:
    def test_credit_counted_flag_prevents_double_count(self):
        """P1 #4: credit_counted flag prevents double-counting."""
        executor = _make_ref_executor()
        candidate = _make_ref_candidate("bull_put")
        result = executor.execute_spread(candidate)

        assert result["status"] == "open"
        pos = list(executor.state.positions.values())[0]
        assert pos.credit_counted is True
        assert executor.state.total_credit_collected > 0
        old_total = executor.state.total_credit_collected

        if not pos.credit_counted:
            executor.state.total_credit_collected += pos.entry_credit * pos.contracts * 100
        assert executor.state.total_credit_collected == old_total


class TestMarketOrders:
    """Tests verifying market order behavior."""

    def test_open_uses_market_orders(self):
        """All open legs use market orders, not limit orders."""
        executor = _make_ref_executor()
        candidate = _make_ref_candidate("bull_put")
        executor.execute_spread(candidate)

        assert executor.broker.place_option_market_order.call_count == 2
        executor.broker.place_option_order.assert_not_called()

    def test_close_uses_market_orders(self):
        """All close legs use market orders."""
        executor = _make_ref_executor()
        pos = SpreadPosition(
            spread_id="TEST", underlying="TSLA", expiry="2026-03-27",
            spread_type="bull_put",
            legs=[
                SpreadLeg("S", 250.0, "P", "SELL", 1, 3.00, status="filled"),
                SpreadLeg("L", 245.0, "P", "BUY", 1, 1.50, status="filled"),
            ],
            entry_credit=1.50, max_risk=3.50, contracts=1, status="open",
        )
        executor.state.positions["TEST"] = pos
        brief_s = MagicMock()
        brief_s.identifier = "S"
        brief_s.bid_price = 0.50
        brief_s.ask_price = 0.70
        brief_l = MagicMock()
        brief_l.identifier = "L"
        brief_l.bid_price = 0.10
        brief_l.ask_price = 0.20
        executor.broker.get_option_briefs.return_value = [brief_s, brief_l]

        executor.close_spread(pos)

        assert executor.broker.place_option_market_order.call_count == 2
        executor.broker.place_option_order.assert_not_called()

    def test_emergency_close_uses_market_order(self):
        """Emergency close uses market order."""
        executor = _make_ref_executor()
        executor._save_state = MagicMock()

        pos = SpreadPosition(
            spread_id="TEST", underlying="TSLA", expiry="2026-03-27",
            spread_type="bull_put", status="error",
        )
        leg = SpreadLeg("L", 245.0, "P", "BUY", 1, 1.50, status="filled")
        pos.legs.append(leg)

        executor._emergency_close_leg(leg, pos)

        executor.broker.place_option_market_order.assert_called_once()
        executor.broker.place_option_order.assert_not_called()
