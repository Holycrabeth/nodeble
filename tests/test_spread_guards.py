# -*- coding: utf-8 -*-
"""Tests for spread execution guards: price guard + delta recheck.

Ported from reference/tiger-trading/tests/test_spread_guards.py
"""

import pytest
from unittest.mock import MagicMock

from nodeble.strategy.executor import SpreadExecutor
from nodeble.core.state import SpreadState
from nodeble.strategy.strike_selector import SpreadCandidate


def _make_candidate(spread_type="bull_put", scan_price=0.0):
    c = SpreadCandidate(
        underlying="SPY", spread_type=spread_type,
        expiry="2026-03-27", dte=10,
    )
    c.scan_price = scan_price
    if spread_type in ("bull_put", "iron_condor"):
        c.short_put_identifier = "SPY  260327P00560000"
        c.short_put_strike = 560.0
        c.short_put_delta = -0.18
        c.short_put_bid = 3.00
        c.long_put_identifier = "SPY  260327P00555000"
        c.long_put_strike = 555.0
        c.long_put_delta = -0.12
        c.long_put_ask = 1.50
        c.put_credit = 1.50
    if spread_type in ("bear_call", "iron_condor"):
        c.short_call_identifier = "SPY  260327C00600000"
        c.short_call_strike = 600.0
        c.short_call_delta = 0.18
        c.short_call_bid = 3.00
        c.long_call_identifier = "SPY  260327C00605000"
        c.long_call_strike = 605.0
        c.long_call_delta = 0.12
        c.long_call_ask = 1.50
        c.call_credit = 1.50
    c.total_credit = 1.50 if spread_type != "iron_condor" else 3.00
    c.spread_width = 5.0
    c.max_risk = 3.50 if spread_type != "iron_condor" else 2.00
    c.contracts = 1
    return c


def _make_brief(identifier, delta):
    """Create a mock option brief with given identifier and delta."""
    brief = MagicMock()
    brief.identifier = identifier
    brief.delta = delta
    return brief


def _make_executor(broker=None, config_overrides=None):
    fresh_broker = broker is None
    broker = broker or MagicMock()
    broker.place_option_order.return_value = 12345
    broker.place_option_market_order.return_value = 12345
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
    if config_overrides:
        for k, v in config_overrides.items():
            if isinstance(v, dict) and k in config:
                config[k].update(v)
            else:
                config[k] = v

    # Only set default safe briefs when no broker was provided by the caller.
    # If caller passed a broker, they already configured get_option_briefs.
    if fresh_broker:
        safe_brief = MagicMock()
        safe_brief.identifier = ""
        safe_brief.delta = -0.18
        broker.get_option_briefs.return_value = [safe_brief]

    executor = SpreadExecutor(broker, notifier, config, state, "/tmp/state_test.json")
    executor.poll_interval = 0.01
    executor._poll_for_fill = MagicMock(return_value="FILLED")
    executor._save_state = MagicMock()

    return executor


# ──────────────────────────────────────────────────
# Price Guard Tests
# ──────────────────────────────────────────────────


class TestPriceGuard:
    def test_price_guard_blocks_execution(self):
        """scan_price=200, current=210 (5%), threshold=3% -> abort."""
        broker = MagicMock()
        broker.get_stock_price.return_value = 210.0
        executor = _make_executor(broker=broker)

        candidate = _make_candidate("bull_put", scan_price=200.0)
        result = executor.execute_spread(candidate)

        assert result["status"] == "aborted_price_guard"
        assert "PRICE GUARD" in result["reason"]
        broker.place_option_market_order.assert_not_called()

    def test_price_guard_allows_execution(self):
        """scan_price=200, current=204 (2%), threshold=3% -> pass."""
        broker = MagicMock()
        broker.get_stock_price.return_value = 204.0
        broker.place_option_order.return_value = 12345
        broker.place_option_market_order.return_value = 12345
        executor = _make_executor(broker=broker)

        candidate = _make_candidate("bull_put", scan_price=200.0)
        result = executor.execute_spread(candidate)

        assert result["status"] == "open"
        assert broker.place_option_market_order.call_count == 2

    def test_price_guard_zero_scan_price_skips(self):
        """scan_price=0 -> skip guard (backward compat)."""
        broker = MagicMock()
        broker.get_stock_price.return_value = 999.0  # would fail if checked
        broker.place_option_order.return_value = 12345
        broker.place_option_market_order.return_value = 12345
        executor = _make_executor(broker=broker)

        candidate = _make_candidate("bull_put", scan_price=0.0)
        result = executor.execute_spread(candidate)

        assert result["status"] == "open"
        broker.get_stock_price.assert_not_called()

    def test_price_guard_blocks_condor(self):
        """Price guard also works for iron condor execution."""
        broker = MagicMock()
        broker.get_stock_price.return_value = 210.0  # 5% above scan
        executor = _make_executor(broker=broker)

        candidate = _make_candidate("iron_condor", scan_price=200.0)
        result = executor.execute_iron_condor(candidate)

        assert result["status"] == "aborted_price_guard"
        broker.place_option_market_order.assert_not_called()

    def test_price_guard_allows_condor(self):
        """Price guard passes for condor within threshold."""
        broker = MagicMock()
        broker.get_stock_price.return_value = 201.0  # 0.5% above scan
        broker.place_option_order.return_value = 12345
        broker.place_option_market_order.return_value = 12345
        executor = _make_executor(broker=broker)

        candidate = _make_candidate("iron_condor", scan_price=200.0)
        result = executor.execute_iron_condor(candidate)

        assert result["status"] == "open"

    def test_price_guard_skipped_on_dry_run(self):
        """Dry run should skip price guard."""
        broker = MagicMock()
        broker.get_stock_price.return_value = 300.0  # would fail if checked
        executor = _make_executor(broker=broker)

        candidate = _make_candidate("bull_put", scan_price=200.0)
        result = executor.execute_spread(candidate, dry_run=True)

        assert result["status"] == "dry_run"
        broker.get_stock_price.assert_not_called()

    def test_price_guard_fails_closed_on_quote_error(self):
        """If get_stock_price raises, guard should fail-closed (abort execution)."""
        broker = MagicMock()
        broker.get_stock_price.side_effect = Exception("API error")
        broker.place_option_order.return_value = 12345
        broker.place_option_market_order.return_value = 12345
        executor = _make_executor(broker=broker)

        candidate = _make_candidate("bull_put", scan_price=200.0)
        result = executor.execute_spread(candidate)

        assert result["status"] == "aborted_price_guard"

    def test_price_guard_downward_move_also_blocks(self):
        """Price drop of >3% should also trigger guard (abs check)."""
        broker = MagicMock()
        broker.get_stock_price.return_value = 190.0  # -5% from scan
        executor = _make_executor(broker=broker)

        candidate = _make_candidate("bull_put", scan_price=200.0)
        result = executor.execute_spread(candidate)

        assert result["status"] == "aborted_price_guard"


# ──────────────────────────────────────────────────
# Delta Guard Tests
# ──────────────────────────────────────────────────


class TestDeltaGuard:
    def test_delta_guard_blocks_execution(self):
        """current_delta=0.40, max=0.30 -> abort."""
        broker = MagicMock()
        broker.get_stock_price.return_value = 200.0  # price guard passes
        broker.get_option_briefs.return_value = [
            _make_brief("SPY  260327P00560000", -0.40),
        ]
        executor = _make_executor(broker=broker)

        candidate = _make_candidate("bull_put", scan_price=200.0)
        result = executor.execute_spread(candidate)

        assert result["status"] == "aborted_delta_guard"
        assert "DELTA GUARD" in result["reason"]
        broker.place_option_market_order.assert_not_called()

    def test_delta_guard_allows_execution(self):
        """current_delta=0.20, max=0.30 -> pass."""
        broker = MagicMock()
        broker.get_stock_price.return_value = 200.0
        broker.get_option_briefs.return_value = [
            _make_brief("SPY  260327P00560000", -0.20),
        ]
        broker.place_option_order.return_value = 12345
        broker.place_option_market_order.return_value = 12345
        executor = _make_executor(broker=broker)

        candidate = _make_candidate("bull_put", scan_price=200.0)
        result = executor.execute_spread(candidate)

        assert result["status"] == "open"

    def test_delta_guard_bear_call(self):
        """Delta guard works on bear call short leg too."""
        broker = MagicMock()
        broker.get_stock_price.return_value = 200.0
        broker.get_option_briefs.return_value = [
            _make_brief("SPY  260327C00600000", 0.45),
        ]
        executor = _make_executor(broker=broker)

        candidate = _make_candidate("bear_call", scan_price=200.0)
        result = executor.execute_spread(candidate)

        assert result["status"] == "aborted_delta_guard"

    def test_condor_delta_guard_both_legs(self):
        """Condor: both short put and short call deltas checked."""
        broker = MagicMock()
        broker.get_stock_price.return_value = 200.0
        # Short put OK, short call blown
        broker.get_option_briefs.return_value = [
            _make_brief("SPY  260327P00560000", -0.15),
            _make_brief("SPY  260327C00600000", 0.45),
        ]
        executor = _make_executor(broker=broker)

        candidate = _make_candidate("iron_condor", scan_price=200.0)
        result = executor.execute_iron_condor(candidate)

        assert result["status"] == "aborted_delta_guard"
        assert "short_call" in result["reason"]
        broker.place_option_market_order.assert_not_called()

    def test_condor_delta_guard_passes_both_legs(self):
        """Condor: both deltas within range -> execute."""
        broker = MagicMock()
        broker.get_stock_price.return_value = 200.0
        broker.get_option_briefs.return_value = [
            _make_brief("SPY  260327P00560000", -0.15),
            _make_brief("SPY  260327C00600000", 0.18),
        ]
        broker.place_option_order.return_value = 12345
        broker.place_option_market_order.return_value = 12345
        executor = _make_executor(broker=broker)

        candidate = _make_candidate("iron_condor", scan_price=200.0)
        result = executor.execute_iron_condor(candidate)

        assert result["status"] == "open"

    def test_delta_guard_fails_closed_on_briefs_error(self):
        """If get_option_briefs raises, guard should fail-closed (abort execution)."""
        broker = MagicMock()
        broker.get_stock_price.return_value = 200.0
        broker.get_option_briefs.side_effect = Exception("API error")
        broker.place_option_order.return_value = 12345
        broker.place_option_market_order.return_value = 12345
        executor = _make_executor(broker=broker)

        candidate = _make_candidate("bull_put", scan_price=200.0)
        result = executor.execute_spread(candidate)

        assert result["status"] == "aborted_delta_guard"

    def test_delta_guard_skipped_on_dry_run(self):
        """Dry run should skip delta guard."""
        broker = MagicMock()
        broker.get_option_briefs.return_value = [
            _make_brief("SPY  260327P00560000", -0.99),  # would fail
        ]
        executor = _make_executor(broker=broker)

        candidate = _make_candidate("bull_put", scan_price=0.0)
        result = executor.execute_spread(candidate, dry_run=True)

        assert result["status"] == "dry_run"
        broker.get_option_briefs.assert_not_called()
