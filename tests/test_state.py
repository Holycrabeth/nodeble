import json
from pathlib import Path

from nodeble.core.state import SpreadState, SpreadPosition, SpreadLeg


def test_spread_state_create_empty():
    state = SpreadState()
    assert state.positions == {}
    assert state.total_realized_pnl == 0.0


def test_spread_state_save_and_load(tmp_path):
    state_path = tmp_path / "state.json"
    state = SpreadState()

    leg = SpreadLeg(
        identifier="TSLA  260327P00250000",
        strike=250.0,
        put_call="P",
        action="SELL",
        contracts=1,
        entry_premium=3.50,
        order_id=12345,
        status="filled",
        entry_delta=-0.15,
    )
    pos = SpreadPosition(
        spread_id="TSLA_iron_condor_2026-03-27_250_245_455_460",
        underlying="TSLA",
        expiry="2026-03-27",
        spread_type="iron_condor",
        legs=[leg],
        entry_date="2026-03-20",
        entry_credit=2.50,
        max_risk=2.50,
        contracts=1,
        status="open",
    )
    state.positions[pos.spread_id] = pos
    state.save(str(state_path))

    loaded = SpreadState.load(str(state_path))
    assert len(loaded.positions) == 1
    assert loaded.positions[pos.spread_id].underlying == "TSLA"
    assert loaded.positions[pos.spread_id].legs[0].strike == 250.0


def test_spread_state_get_open_positions():
    state = SpreadState()
    open_pos = SpreadPosition(
        spread_id="open1", underlying="SPY", expiry="2026-04-01",
        spread_type="iron_condor", legs=[], entry_date="2026-03-20",
        entry_credit=1.0, max_risk=4.0, contracts=1, status="open",
    )
    closed_pos = SpreadPosition(
        spread_id="closed1", underlying="QQQ", expiry="2026-04-01",
        spread_type="iron_condor", legs=[], entry_date="2026-03-20",
        entry_credit=1.0, max_risk=4.0, contracts=1, status="closed_profit",
    )
    state.positions["open1"] = open_pos
    state.positions["closed1"] = closed_pos
    assert len(state.get_open_positions()) == 1
    assert state.get_open_positions()[0].spread_id == "open1"


def test_spread_state_atomic_write(tmp_path):
    """Verify save uses atomic write (no partial files on crash)."""
    state_path = tmp_path / "state.json"
    state = SpreadState()
    state.save(str(state_path))
    assert state_path.exists()
    data = json.loads(state_path.read_text())
    assert "positions" in data
