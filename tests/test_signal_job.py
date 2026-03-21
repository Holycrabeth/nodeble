import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from nodeble.signals.signal_job import write_signal_state, read_signal_state


def test_write_and_read_signal_state(tmp_path):
    """Write signal state -> read it back -> matches."""
    state_path = str(tmp_path / "signal_state.json")
    state = {
        "version": 1,
        "generated_at": datetime.now(ZoneInfo("America/New_York")).isoformat(),
        "vix": 18.5,
        "vix_tier": "15-20",
        "vix_fallback": False,
        "symbols": {
            "SPY": {
                "bull_share": 0.35,
                "decision": "SELL",
                "confidence": 0.30,
            }
        },
    }
    write_signal_state(state, state_path)

    loaded = read_signal_state(state_path)
    assert loaded is not None
    assert loaded["vix"] == 18.5
    assert loaded["symbols"]["SPY"]["bull_share"] == 0.35


def test_read_missing_file_returns_none(tmp_path):
    """Missing file -> returns None."""
    result = read_signal_state(str(tmp_path / "nonexistent.json"))
    assert result is None


def test_read_stale_file_returns_none(tmp_path):
    """File older than 24h -> returns None."""
    state_path = str(tmp_path / "signal_state.json")
    old_time = (datetime.now(ZoneInfo("America/New_York")) - timedelta(hours=25)).isoformat()
    state = {
        "version": 1,
        "generated_at": old_time,
        "vix": 18.5,
        "symbols": {},
    }
    write_signal_state(state, state_path)

    result = read_signal_state(state_path)
    assert result is None
