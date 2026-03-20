"""Prove that dry-run mode CANNOT place real orders.

Two independent safety layers:
1. MockBroker — test double that records but never sends orders
2. Executor dry_run flag — skips order placement entirely
"""
from nodeble.strategy.executor import SpreadExecutor
from nodeble.core.state import SpreadState, SpreadPosition, SpreadLeg
from nodeble.strategy.strike_selector import SpreadCandidate
from mock_broker import MockBroker


def _make_candidate():
    c = SpreadCandidate(underlying="SPY", spread_type="iron_condor", expiry="2026-04-01", dte=30)
    c.contracts = 1
    c.scan_price = 500.0
    c.total_credit = 2.50
    c.max_risk = 2.50
    return c


def test_dry_run_executor_places_zero_orders(tmp_path):
    """Layer 2: executor dry_run=True never calls broker."""
    broker = MockBroker()
    state = SpreadState()
    executor = SpreadExecutor(
        broker=broker, notifier=None,
        config={"execution": {"fill_timeout_sec": 1, "allow_degradation": False}},
        state=state, state_path=str(tmp_path / "state.json"),
    )
    result = executor.execute_iron_condor(_make_candidate(), dry_run=True)
    assert result["status"] == "dry_run"
    assert broker.orders_placed == []
    assert broker.orders_cancelled == []


def test_mock_broker_records_but_never_sends():
    """Layer 1: MockBroker tracks calls but never touches real API."""
    broker = MockBroker()
    oid = broker.place_option_market_order("SPY  260401P00490000", "SELL", 1)
    assert len(broker.orders_placed) == 1
    assert broker.get_order(oid).status == "FILLED"


def test_close_spread_dry_run(tmp_path):
    """Closing in dry-run also places zero orders."""
    broker = MockBroker()
    state = SpreadState()
    pos = SpreadPosition(
        spread_id="test", underlying="SPY", expiry="2026-04-01",
        spread_type="iron_condor", legs=[
            SpreadLeg("SPY_P245", 245, "P", "BUY", 1, 1.0, 1, "filled", -0.10),
            SpreadLeg("SPY_P250", 250, "P", "SELL", 1, 3.0, 2, "filled", -0.15),
        ],
        entry_date="2026-03-20", entry_credit=2.0, max_risk=3.0,
        contracts=1, status="open",
    )
    state.positions["test"] = pos
    executor = SpreadExecutor(
        broker=broker, notifier=None,
        config={"execution": {"fill_timeout_sec": 1}},
        state=state, state_path=str(tmp_path / "state.json"),
    )
    result = executor.close_spread(pos, dry_run=True)
    assert result["status"] == "dry_run"
    assert broker.orders_placed == []
