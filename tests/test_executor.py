from nodeble.strategy.executor import SpreadExecutor
from nodeble.core.state import SpreadState
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
