# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from nodeble.strategy.manager import (
    evaluate_positions,
    verify_pending_fills,
    cleanup_stale_orders,
    SpreadAction,
)
from nodeble.core.state import SpreadState, SpreadPosition, SpreadLeg


def test_evaluate_empty_state():
    state = SpreadState()
    cfg = {
        "management": {
            "profit_take_pct": 0.50,
            "stop_loss_pct": 2.0,
            "close_before_dte": 1,
        }
    }
    actions = evaluate_positions(state=state, broker=None, strategy_cfg=cfg)
    assert actions == []


# ──────────────────────────────────────────────────────────────────
# Ported from reference/tiger-trading/tests/test_options_manager.py
# ──────────────────────────────────────────────────────────────────


def _make_position(spread_id="TEST", status="open", entry_credit=1.50):
    return SpreadPosition(
        spread_id=spread_id,
        underlying="TSLA",
        expiry="2026-03-27",
        spread_type="bull_put",
        legs=[
            SpreadLeg("S", 250.0, "P", "SELL", 1, 3.00, order_id=100, status="filled"),
            SpreadLeg("L", 245.0, "P", "BUY", 1, 1.50, order_id=101, status="filled"),
        ],
        entry_credit=entry_credit,
        max_risk=3.50,
        contracts=1,
        status=status,
    )


class TestCleanupStaleOrders:
    def test_no_pending_orders(self):
        broker = MagicMock()
        state = SpreadState()
        cancelled = cleanup_stale_orders(broker, state)
        assert cancelled == []
        broker.get_open_orders.assert_not_called()

    def test_cancel_pending_spread_orders(self):
        broker = MagicMock()
        state = SpreadState()
        pos = _make_position(status="pending")
        pos.legs[0].status = "pending"
        pos.legs[0].order_id = 999
        state.positions["TEST"] = pos

        order = MagicMock()
        order.id = 999
        broker.get_open_orders.return_value = [order]

        cancelled = cleanup_stale_orders(broker, state)
        assert 999 in cancelled
        broker.cancel_order.assert_called_with(999)

    def test_skip_non_spread_orders(self):
        broker = MagicMock()
        state = SpreadState()
        pos = _make_position(status="pending")
        pos.legs[0].status = "pending"
        pos.legs[0].order_id = 999
        state.positions["TEST"] = pos

        order1 = MagicMock()
        order1.id = 888
        order2 = MagicMock()
        order2.id = 999
        broker.get_open_orders.return_value = [order1, order2]

        cancelled = cleanup_stale_orders(broker, state)
        assert 888 not in cancelled
        assert 999 in cancelled

    def test_dry_run(self):
        broker = MagicMock()
        state = SpreadState()
        pos = _make_position(status="pending")
        pos.legs[0].status = "pending"
        pos.legs[0].order_id = 999
        state.positions["TEST"] = pos

        order = MagicMock()
        order.id = 999
        broker.get_open_orders.return_value = [order]

        cancelled = cleanup_stale_orders(broker, state, dry_run=True)
        assert 999 in cancelled
        broker.cancel_order.assert_not_called()


class TestVerifyPendingFills:
    def test_all_filled(self):
        broker = MagicMock()
        state = SpreadState()
        pos = _make_position(status="pending")
        pos.legs[0].status = "pending"
        pos.legs[1].status = "pending"
        state.positions["TEST"] = pos

        order = MagicMock()
        order.status = "FILLED"
        broker.get_order.return_value = order

        result = verify_pending_fills(broker, state)
        assert result["confirmed"] == 1
        assert pos.status == "open"

    def test_all_cancelled_removes_phantom(self):
        broker = MagicMock()
        state = SpreadState()
        pos = SpreadPosition(
            spread_id="PHANTOM", underlying="TSLA", expiry="2026-03-27",
            spread_type="bull_put",
            legs=[
                SpreadLeg("S", 250.0, "P", "SELL", 1, 3.0, order_id=100, status="pending"),
                SpreadLeg("L", 245.0, "P", "BUY", 1, 1.5, order_id=101, status="pending"),
            ],
            status="pending",
        )
        state.positions["PHANTOM"] = pos

        order = MagicMock()
        order.status = "CANCELLED"
        broker.get_order.return_value = order

        result = verify_pending_fills(broker, state)
        assert result["removed"] == 1
        assert "PHANTOM" not in state.positions

    def test_partial_fill(self):
        broker = MagicMock()
        state = SpreadState()
        pos = SpreadPosition(
            spread_id="PARTIAL", underlying="TSLA", expiry="2026-03-27",
            spread_type="bull_put",
            legs=[
                SpreadLeg("S", 250.0, "P", "SELL", 1, 3.0, order_id=100, status="pending"),
                SpreadLeg("L", 245.0, "P", "BUY", 1, 1.5, order_id=101, status="pending"),
            ],
            status="pending",
        )
        state.positions["PARTIAL"] = pos

        def get_order_side_effect(order_id):
            order = MagicMock()
            order.status = "FILLED" if order_id == 100 else "CANCELLED"
            return order

        broker.get_order.side_effect = get_order_side_effect

        result = verify_pending_fills(broker, state)
        assert result["partial"] == 1
        assert state.positions["PARTIAL"].status == "partial"


class TestEvaluatePositions:
    def _mock_broker_with_quotes(self, bid_s=0.50, ask_s=0.70, bid_l=0.10, ask_l=0.20):
        broker = MagicMock()
        brief_s = MagicMock()
        brief_s.identifier = "S"
        brief_s.bid_price = bid_s
        brief_s.ask_price = ask_s
        brief_l = MagicMock()
        brief_l.identifier = "L"
        brief_l.bid_price = bid_l
        brief_l.ask_price = ask_l
        broker.get_option_briefs.return_value = [brief_s, brief_l]
        return broker

    def test_profit_target_triggered(self):
        state = SpreadState()
        pos = _make_position(entry_credit=1.50)
        state.positions["TEST"] = pos
        broker = self._mock_broker_with_quotes(bid_s=0.20, ask_s=0.30, bid_l=0.05, ask_l=0.10)

        strategy_cfg = {"management": {"profit_take_pct": 0.50, "stop_loss_pct": 2.0, "close_before_dte": 1}}
        actions = evaluate_positions(state, broker, strategy_cfg)

        assert len(actions) == 1
        assert actions[0].action == "close_profit"

    def test_stop_loss_triggered(self):
        state = SpreadState()
        pos = _make_position(entry_credit=1.50)
        state.positions["TEST"] = pos
        broker = self._mock_broker_with_quotes(bid_s=3.00, ask_s=3.50, bid_l=0.10, ask_l=0.20)

        strategy_cfg = {"management": {"profit_take_pct": 0.50, "stop_loss_pct": 2.0, "close_before_dte": 1}}
        actions = evaluate_positions(state, broker, strategy_cfg)

        assert len(actions) == 1
        assert actions[0].action == "close_stop"

    def test_dte_close(self):
        from datetime import date as real_date, timedelta
        state = SpreadState()
        pos = _make_position(entry_credit=1.50)
        tomorrow = (real_date.today() + timedelta(days=1)).isoformat()
        pos.expiry = tomorrow
        state.positions["TEST"] = pos
        broker = self._mock_broker_with_quotes(bid_s=0.80, ask_s=1.00, bid_l=0.10, ask_l=0.20)

        strategy_cfg = {"management": {"profit_take_pct": 0.50, "stop_loss_pct": 2.0, "close_before_dte": 1}}
        actions = evaluate_positions(state, broker, strategy_cfg)

        assert len(actions) == 1
        assert actions[0].action == "close_dte"

    def test_holding_no_action(self):
        state = SpreadState()
        pos = _make_position(entry_credit=1.50)
        state.positions["TEST"] = pos
        broker = self._mock_broker_with_quotes(bid_s=0.80, ask_s=1.00, bid_l=0.10, ask_l=0.20)

        strategy_cfg = {"management": {"profit_take_pct": 0.50, "stop_loss_pct": 2.0, "close_before_dte": 1}}
        actions = evaluate_positions(state, broker, strategy_cfg)

        assert len(actions) == 0

    def test_no_open_positions(self):
        state = SpreadState()
        broker = MagicMock()
        strategy_cfg = {"management": {}}
        actions = evaluate_positions(state, broker, strategy_cfg)
        assert actions == []

    @patch("nodeble.strategy.manager.options_risk.verify_no_naked_legs", return_value=False)
    def test_naked_leg_emergency_close(self, mock_verify):
        state = SpreadState()
        pos = _make_position(entry_credit=1.50)
        state.positions["TEST"] = pos
        broker = self._mock_broker_with_quotes()

        strategy_cfg = {"management": {"profit_take_pct": 0.50, "stop_loss_pct": 2.0, "close_before_dte": 1}}
        actions = evaluate_positions(state, broker, strategy_cfg)

        assert len(actions) == 1
        assert actions[0].action == "close_stop"
        assert "NAKED" in actions[0].reason
