# NODEBLE Phase 1 Extraction — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the Iron Condor factory from `reference/tiger-trading` into a standalone `nodeble` Python package deployable on a friend's VPS.

**Architecture:** Copy ~4,000 lines of IC factory code into `src/nodeble/`, fix import paths, add `~/.nodeble/` config/data directory convention, wire up CLI entry point + deploy script. TDD — port ~1,969 lines of existing tests.

**Tech Stack:** Python 3.12+, uv, pytest, tigeropen, pandas, numpy, yfinance, pyarrow, pyyaml, pandas-market-calendars, python-telegram-bot

**Spec:** `docs/superpowers/specs/2026-03-20-nodeble-extraction-design.md`

**Reference source:** `reference/tiger-trading/` — do NOT modify files in this directory.

**Import rewrite rule:** Every extraction task follows the same pattern — copy file, apply these import prefix changes:
- `from options.` → `from nodeble.strategy.` (exception: `options.state` → `from nodeble.core.state`)
- `from options import risk` → `from nodeble.core import risk`
- `from engine.audit` → `from nodeble.core.audit`
- `from engine.` → `from nodeble.engine.`
- `from data.` → `from nodeble.data.`
- `from src.broker` → `from nodeble.core.broker`
- `from src.notify` → `from nodeble.notify.telegram`

**Config/data path convention:** All user data under `~/.nodeble/`. Modules should accept paths as parameters or use a `get_data_dir()` helper that returns `Path.home() / ".nodeble"`.

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/nodeble/__init__.py`
- Create: `src/nodeble/core/__init__.py`
- Create: `src/nodeble/strategy/__init__.py`
- Create: `src/nodeble/data/__init__.py`
- Create: `src/nodeble/engine/__init__.py`
- Create: `src/nodeble/notify/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "nodeble"
version = "0.1.0"
description = "Iron Condor trading automation"
requires-python = ">=3.12"
dependencies = [
    "tigeropen",
    "pyyaml",
    "yfinance",
    "pandas",
    "numpy",
    "pyarrow",
    "pandas-market-calendars",
    "requests",
    "python-telegram-bot",
]

[project.optional-dependencies]
dev = ["pytest", "pytest-cov"]

[tool.hatch.build.targets.wheel]
packages = ["src/nodeble"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src", "tests"]
```

- [ ] **Step 2: Create all `__init__.py` files**

All `__init__.py` files should be empty. Create these:
- `src/nodeble/__init__.py`
- `src/nodeble/core/__init__.py`
- `src/nodeble/strategy/__init__.py`
- `src/nodeble/data/__init__.py`
- `src/nodeble/engine/__init__.py`
- `src/nodeble/notify/__init__.py`
- `tests/__init__.py`

- [ ] **Step 3: Create `tests/conftest.py`**

```python
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / "fixtures"
```

- [ ] **Step 4: Create `src/nodeble/paths.py`**

Shared helper for `~/.nodeble/` directory convention:

```python
from pathlib import Path


def get_data_dir() -> Path:
    """Return ~/.nodeble/ data directory, creating it if needed."""
    data_dir = Path.home() / ".nodeble"
    data_dir.mkdir(exist_ok=True)
    return data_dir


def get_config_dir() -> Path:
    config_dir = get_data_dir() / "config"
    config_dir.mkdir(exist_ok=True)
    return config_dir
```

- [ ] **Step 5: Install project in dev mode**

```bash
cd /home/mayongtao/projects/nodeble
uv venv
uv pip install -e ".[dev]"
```

- [ ] **Step 6: Verify basic import works**

```bash
uv run python -c "import nodeble; print('OK')"
```

Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/ tests/
git commit -m "feat: scaffold nodeble project structure"
```

---

### Task 2: Core foundation — state_lock, audit, state

**Files:**
- Create: `src/nodeble/core/state_lock.py` (from `reference/tiger-trading/engine/state_lock.py`)
- Create: `src/nodeble/core/audit.py` (from `reference/tiger-trading/engine/audit.py`)
- Create: `src/nodeble/core/state.py` (from `reference/tiger-trading/options/state.py`)
- Create: `tests/test_state.py`

- [ ] **Step 1: Extract `state_lock.py`**

Copy `reference/tiger-trading/engine/state_lock.py` → `src/nodeble/core/state_lock.py`.
No import changes needed — this file has zero internal imports (only stdlib: `fcntl`, `logging`, `time`, `contextlib`, `pathlib`).

- [ ] **Step 2: Extract `audit.py`**

Copy `reference/tiger-trading/engine/audit.py` → `src/nodeble/core/audit.py`.
No internal import changes needed (only stdlib: `json`, `logging`, `datetime`, `pathlib`, `zoneinfo`).

Fix the data path: find the hardcoded audit directory path and replace with:
```python
from nodeble.paths import get_data_dir
# Replace any hardcoded "data/audit" with:
audit_dir = get_data_dir() / "data" / "audit"
```

- [ ] **Step 3: Extract `state.py`**

Copy `reference/tiger-trading/options/state.py` → `src/nodeble/core/state.py`.

Fix the ONE internal import — the lazy import of `state_lock` inside the `save()` method. Find:
```python
from engine.state_lock import state_lock
```
Replace with:
```python
from nodeble.core.state_lock import state_lock
```

Also fix the default state path constant if present. Find any `"data/state_options.json"` and replace with a parameter or `get_data_dir()` usage.

- [ ] **Step 4: Write state tests**

Create `tests/test_state.py`:

```python
import json
import tempfile
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
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_state.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/nodeble/core/state_lock.py src/nodeble/core/audit.py src/nodeble/core/state.py tests/test_state.py
git commit -m "feat: extract core foundation — state, state_lock, audit"
```

---

### Task 3: BrokerAdapter protocol + MockBroker

**Files:**
- Create: `src/nodeble/core/broker.py` (new — protocol definition only, NOT the TigerBroker yet)
- Create: `tests/mock_broker.py`

- [ ] **Step 1: Create BrokerAdapter protocol**

Create `src/nodeble/core/broker.py`:

```python
"""Broker adapter protocol and helpers.

TigerBroker implementation is loaded lazily to avoid importing tigeropen
at module level. MockBroker in tests/ provides a test double.
"""
import logging
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class BrokerAdapter(Protocol):
    """Methods the IC pipeline calls on any broker."""

    def get_option_analysis(self, symbols: list[str]) -> list: ...
    def get_stock_price(self, symbol: str) -> float: ...
    def get_option_expirations(self, symbol: str) -> list[dict]: ...
    def get_option_chain(self, symbol: str, expiry: str, option_filter: dict | None = None) -> list[dict]: ...
    def get_option_briefs(self, identifiers: list[str]) -> list: ...
    def place_option_market_order(self, identifier: str, action: str, quantity: int) -> int: ...
    def get_order(self, order_id: int) -> object: ...
    def cancel_order(self, order_id: int) -> None: ...
    def get_open_orders(self, sec_type: str = "OPT") -> list: ...
    def get_assets(self) -> object: ...
    def get_positions(self, sec_type: str = "OPT") -> list: ...
```

- [ ] **Step 2: Create MockBroker**

Create `tests/mock_broker.py`. This is a minimal test double — NOT the SnapshotBroker from backtesting (that's extracted in Task 13):

```python
"""Minimal mock broker for unit tests.

Returns configurable canned data. Order placement records calls
for assertion in tests but never touches a real API.
"""
from dataclasses import dataclass, field


@dataclass
class MockSegment:
    cash_available_for_trade: float = 100_000.0
    net_liquidation: float = 200_000.0


@dataclass
class MockAssets:
    segments: dict = field(default_factory=lambda: {"S": MockSegment()})


@dataclass
class MockBrief:
    identifier: str = ""
    bid_price: float = 0.0
    ask_price: float = 0.0
    delta: float = 0.0
    latest_price: float = 0.0


@dataclass
class MockOrder:
    status: str = "FILLED"


class MockBroker:
    """Test double implementing BrokerAdapter protocol."""

    def __init__(self):
        self.orders_placed: list[dict] = []
        self.orders_cancelled: list[int] = []
        self._next_order_id = 1000
        self._order_statuses: dict[int, str] = {}
        self._stock_prices: dict[str, float] = {}
        self._option_analyses: list = []
        self._option_chains: dict[str, list[dict]] = {}
        self._option_expirations: dict[str, list[dict]] = {}
        self._option_briefs: dict[str, MockBrief] = {}
        self._assets = MockAssets()

    def get_option_analysis(self, symbols):
        return self._option_analyses

    def get_stock_price(self, symbol):
        return self._stock_prices.get(symbol, 100.0)

    def get_option_expirations(self, symbol):
        return self._option_expirations.get(symbol, [])

    def get_option_chain(self, symbol, expiry, option_filter=None):
        key = f"{symbol}_{expiry}"
        return self._option_chains.get(key, [])

    def get_option_briefs(self, identifiers):
        return [self._option_briefs.get(i, MockBrief(identifier=i)) for i in identifiers]

    def place_option_market_order(self, identifier, action, quantity):
        order_id = self._next_order_id
        self._next_order_id += 1
        self.orders_placed.append({
            "identifier": identifier, "action": action,
            "quantity": quantity, "order_id": order_id,
        })
        self._order_statuses[order_id] = "FILLED"
        return order_id

    def get_order(self, order_id):
        status = self._order_statuses.get(order_id, "FILLED")
        return MockOrder(status=status)

    def cancel_order(self, order_id):
        self.orders_cancelled.append(order_id)

    def get_open_orders(self, sec_type="OPT"):
        return []

    def get_assets(self):
        return self._assets

    def get_positions(self, sec_type="OPT"):
        return []
```

- [ ] **Step 3: Write MockBroker test**

Add to `tests/test_state.py` or create `tests/test_mock_broker.py`:

```python
from mock_broker import MockBroker
from nodeble.core.broker import BrokerAdapter


def test_mock_broker_implements_protocol():
    broker = MockBroker()
    assert isinstance(broker, BrokerAdapter)


def test_mock_broker_tracks_orders():
    broker = MockBroker()
    oid = broker.place_option_market_order("TSLA  260327P00250000", "SELL", 1)
    assert len(broker.orders_placed) == 1
    assert broker.get_order(oid).status == "FILLED"
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/nodeble/core/broker.py tests/mock_broker.py tests/test_mock_broker.py
git commit -m "feat: add BrokerAdapter protocol and MockBroker test double"
```

---

### Task 4: Risk engine + calendar

**Files:**
- Create: `src/nodeble/core/risk.py` (from `reference/tiger-trading/options/risk.py`)
- Create: `src/nodeble/core/calendar.py` (from `reference/tiger-trading/run_execution_job.py`, just `is_market_open()`)
- Create: `tests/test_risk.py`

- [ ] **Step 1: Extract `risk.py`**

Copy `reference/tiger-trading/options/risk.py` → `src/nodeble/core/risk.py`.

Fix imports — find:
```python
from options.state import SpreadState, SpreadPosition
```
Replace with:
```python
from nodeble.core.state import SpreadState, SpreadPosition
```

Remove the hardcoded `"config_options/risk.yaml"` default path. The `load_risk_config()` function should require an explicit path parameter (no default).

- [ ] **Step 2: Extract `calendar.py`**

Create `src/nodeble/core/calendar.py` with just the `is_market_open()` function:

```python
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

NY = ZoneInfo("America/New_York")


def is_market_open() -> bool:
    """Check if US market is currently open (NYSE hours, trading day).

    Fail-open: returns True on error so library/import issues
    don't silently block all live executions.
    """
    try:
        import pandas_market_calendars as mcal
        nyse = mcal.get_calendar("NYSE")
        now_ny = datetime.now(NY)
        today = now_ny.date()
        schedule = nyse.schedule(start_date=today, end_date=today)
        if schedule.empty:
            return False
        market_open = schedule.iloc[0]["market_open"].to_pydatetime()
        market_close = schedule.iloc[0]["market_close"].to_pydatetime()
        return market_open <= now_ny <= market_close
    except Exception as e:
        logger.warning(f"Market hours check failed (allowing execution): {e}")
        return True
```

- [ ] **Step 3: Write risk tests**

Create `tests/test_risk.py`:

```python
from unittest.mock import MagicMock

from nodeble.core.state import SpreadState, SpreadPosition, SpreadLeg
from nodeble.core import risk as options_risk


def _make_risk_cfg():
    """Risk config is a FLAT dict — no 'risk' wrapper. load_risk_config() handles flattening."""
    return {
        "kill_switch": False,
        "min_cash_floor": 20000,
        "max_concurrent_spreads": 10,
        "max_spreads_per_symbol": 2,
        "max_daily_orders": 16,
        "max_daily_loss": 1500,
        "max_total_exposure": 20000,
        "max_portfolio_delta": 200,
    }


def test_kill_switch_off():
    cfg = _make_risk_cfg()
    assert options_risk.check_kill_switch(cfg) is True


def test_kill_switch_on():
    cfg = _make_risk_cfg()
    cfg["kill_switch"] = True
    assert options_risk.check_kill_switch(cfg) is False


def test_max_spreads_under_limit():
    cfg = _make_risk_cfg()
    state = SpreadState()
    assert options_risk.check_max_spreads(state, cfg) is True


def test_max_spreads_at_limit():
    cfg = _make_risk_cfg()
    cfg["max_concurrent_spreads"] = 0
    state = SpreadState()
    pos = SpreadPosition(
        spread_id="test", underlying="SPY", expiry="2026-04-01",
        spread_type="iron_condor", legs=[], entry_date="2026-03-20",
        entry_credit=1.0, max_risk=4.0, contracts=1, status="open",
    )
    state.positions["test"] = pos
    assert options_risk.check_max_spreads(state, cfg) is False


def test_verify_no_naked_legs_covered():
    """A position with matching BUY/SELL legs is not naked."""
    pos = SpreadPosition(
        spread_id="test", underlying="SPY", expiry="2026-04-01",
        spread_type="bull_put", legs=[
            SpreadLeg(identifier="SPY_P250", strike=250, put_call="P",
                      action="SELL", contracts=1, entry_premium=3.0,
                      order_id=1, status="filled", entry_delta=-0.15),
            SpreadLeg(identifier="SPY_P245", strike=245, put_call="P",
                      action="BUY", contracts=1, entry_premium=1.0,
                      order_id=2, status="filled", entry_delta=-0.10),
        ],
        entry_date="2026-03-20", entry_credit=2.0, max_risk=3.0,
        contracts=1, status="open",
    )
    assert options_risk.verify_no_naked_legs(pos) is True
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_risk.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/nodeble/core/risk.py src/nodeble/core/calendar.py tests/test_risk.py
git commit -m "feat: extract risk engine and calendar utility"
```

---

### Task 5: Data layer

**Files:**
- Create: `src/nodeble/data/cache.py` (from `reference/tiger-trading/data/cache.py`)
- Create: `src/nodeble/data/fetcher.py` (from `reference/tiger-trading/data/fetcher.py`)
- Create: `src/nodeble/data/vix.py` (from `reference/tiger-trading/data/vix.py`)
- Create: `src/nodeble/data/chain_recorder.py` (from `reference/tiger-trading/data/chain_recorder.py`)

- [ ] **Step 1: Extract `cache.py`**

Copy `reference/tiger-trading/data/cache.py` → `src/nodeble/data/cache.py`.
No internal import changes needed (only `logging`, `time`, `pathlib`, `pandas`).

Fix the hardcoded cache directory `"data/cache"` to use:
```python
from nodeble.paths import get_data_dir
# Default: get_data_dir() / "data" / "cache"
```

- [ ] **Step 2: Extract `fetcher.py`**

Copy `reference/tiger-trading/data/fetcher.py` → `src/nodeble/data/fetcher.py`.
No internal import changes needed (only `logging`, `datetime`, `pandas`).
Note: the `broker` parameter is passed in, no import coupling.

- [ ] **Step 3: Extract `vix.py`**

Copy `reference/tiger-trading/data/vix.py` → `src/nodeble/data/vix.py`.
No import changes needed (only `copy`, `logging`, `yfinance`).

- [ ] **Step 4: Extract `chain_recorder.py`**

Copy `reference/tiger-trading/data/chain_recorder.py` → `src/nodeble/data/chain_recorder.py`.
No internal import changes needed (only `json`, `logging`, `datetime`, `pathlib`).

Fix the hardcoded snapshot directory to use:
```python
from nodeble.paths import get_data_dir
# Default: get_data_dir() / "data" / "chain_snapshots"
```

- [ ] **Step 5: Smoke test imports**

```bash
uv run python -c "
from nodeble.data.cache import DataCache
from nodeble.data.fetcher import DataFetcher
from nodeble.data.vix import get_vix
from nodeble.data.chain_recorder import record_chain_snapshot
print('All data imports OK')
"
```

Expected: `All data imports OK`

- [ ] **Step 6: Commit**

```bash
git add src/nodeble/data/
git commit -m "feat: extract data layer — cache, fetcher, vix, chain_recorder"
```

---

### Task 6: Strategy utilities — strike_selector, chain_screener

**Files:**
- Create: `src/nodeble/strategy/strike_selector.py` (from `reference/tiger-trading/options/strike_selector.py`)
- Create: `src/nodeble/strategy/chain_screener.py` (from `reference/tiger-trading/options/chain_screener.py`)
- Create: `tests/test_strike_selector.py`

- [ ] **Step 1: Extract `strike_selector.py`**

Copy `reference/tiger-trading/options/strike_selector.py` → `src/nodeble/strategy/strike_selector.py`.
No import changes needed — this file only imports `logging` and `dataclasses`.

- [ ] **Step 2: Extract `chain_screener.py`**

Copy `reference/tiger-trading/options/chain_screener.py` → `src/nodeble/strategy/chain_screener.py`.
No top-level internal imports (only `logging`, `datetime`, `numpy`).

Fix lazy imports inside functions. Search for all occurrences of:
```python
from data.cache import DataCache
```
Replace with:
```python
from nodeble.data.cache import DataCache
```

- [ ] **Step 3: Write strike_selector tests**

Create `tests/test_strike_selector.py`:

```python
from nodeble.strategy.strike_selector import (
    get_spread_width,
    select_put_spread_strikes,
    select_call_spread_strikes,
    build_candidate,
    SpreadCandidate,
)


def test_spread_width_tiers():
    cfg = {"sizing": {"spread_width_rules": [
        {"max_price": 200, "width": 5},
        {"max_price": 500, "width": 10},
        {"max_price": 999999, "width": 15},
    ]}}
    assert get_spread_width(150.0, cfg) == 5
    assert get_spread_width(300.0, cfg) == 10
    assert get_spread_width(600.0, cfg) == 15


def test_spread_candidate_fields():
    c = SpreadCandidate()
    assert hasattr(c, "underlying")
    assert hasattr(c, "total_credit")
    assert hasattr(c, "max_risk")
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_strike_selector.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/nodeble/strategy/strike_selector.py src/nodeble/strategy/chain_screener.py tests/test_strike_selector.py
git commit -m "feat: extract strategy utilities — strike_selector, chain_screener"
```

---

### Task 7: Engine modules + notify

**Files:**
- Create: `src/nodeble/engine/circuit_breaker.py` (from `reference/tiger-trading/engine/circuit_breaker.py`)
- Create: `src/nodeble/engine/kill_switch.py` (from `reference/tiger-trading/engine/kill_switch.py`)
- Create: `src/nodeble/notify/telegram.py` (from `reference/tiger-trading/src/notify.py`)

- [ ] **Step 1: Extract `circuit_breaker.py`**

Copy `reference/tiger-trading/engine/circuit_breaker.py` → `src/nodeble/engine/circuit_breaker.py`.
No internal import changes (only stdlib: `json`, `logging`, `datetime`, `pathlib`, `zoneinfo`).

Fix the `__file__`-relative path. Find:
```python
PROJECT_ROOT = Path(__file__).resolve().parent.parent
```
Replace with:
```python
from nodeble.paths import get_data_dir
```
And update the state file path to use `get_data_dir() / "data" / "circuit_breaker.json"`.

- [ ] **Step 2: Extract `kill_switch.py`**

Copy `reference/tiger-trading/engine/kill_switch.py` → `src/nodeble/engine/kill_switch.py`.

Fix import:
```python
from engine.audit import log_event
```
→
```python
from nodeble.core.audit import log_event
```

- [ ] **Step 3: Extract `telegram.py`**

Copy `reference/tiger-trading/src/notify.py` → `src/nodeble/notify/telegram.py`.
No internal import changes (only `html`, `logging`, `re`, `requests`, `yaml`).

Fix any hardcoded config path for Telegram credentials to accept a path parameter or use `get_config_dir() / "notify.yaml"`.

- [ ] **Step 4: Smoke test imports**

```bash
uv run python -c "
from nodeble.engine.circuit_breaker import CircuitBreaker
from nodeble.engine.kill_switch import cancel_pending_orders
from nodeble.notify.telegram import TelegramNotifier
print('Engine + notify imports OK')
"
```

Expected: `Engine + notify imports OK`

- [ ] **Step 5: Commit**

```bash
git add src/nodeble/engine/ src/nodeble/notify/
git commit -m "feat: extract engine modules and telegram notifier"
```

---

### Task 8: Strategy execution — executor, manager

**Files:**
- Create: `src/nodeble/strategy/executor.py` (from `reference/tiger-trading/options/executor.py`)
- Create: `src/nodeble/strategy/manager.py` (from `reference/tiger-trading/options/manager.py`)
- Create: `tests/test_executor.py`
- Create: `tests/test_manager.py`

- [ ] **Step 1: Extract `executor.py`**

Copy `reference/tiger-trading/options/executor.py` → `src/nodeble/strategy/executor.py`.

Fix imports:
```python
from options.state import SpreadState, SpreadPosition, SpreadLeg
from options.strike_selector import SpreadCandidate
from options import risk as options_risk
from engine.audit import log_event
```
→
```python
from nodeble.core.state import SpreadState, SpreadPosition, SpreadLeg
from nodeble.strategy.strike_selector import SpreadCandidate
from nodeble.core import risk as options_risk
from nodeble.core.audit import log_event
```

- [ ] **Step 2: Extract `manager.py`**

Copy `reference/tiger-trading/options/manager.py` → `src/nodeble/strategy/manager.py`.

Fix imports:
```python
from options.state import SpreadState, SpreadPosition
from options import risk as options_risk
from engine.audit import log_event
```
→
```python
from nodeble.core.state import SpreadState, SpreadPosition
from nodeble.core import risk as options_risk
from nodeble.core.audit import log_event
```

- [ ] **Step 3: Write executor dry-run test**

Create `tests/test_executor.py`:

```python
from unittest.mock import MagicMock

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


def test_executor_dry_run(tmp_path):
    executor = _make_executor(tmp_path=tmp_path)
    candidate = SpreadCandidate()
    candidate.underlying = "SPY"
    candidate.spread_type = "iron_condor"
    candidate.expiry = "2026-04-01"
    candidate.contracts = 1
    result = executor.execute_iron_condor(candidate, dry_run=True)
    assert result["status"] == "dry_run"
    assert executor.broker.orders_placed == []


def test_executor_no_real_orders_in_dry_run(tmp_path):
    """Verify dry-run mode never calls place_option_market_order."""
    broker = MockBroker()
    executor = _make_executor(broker=broker, tmp_path=tmp_path)
    candidate = SpreadCandidate()
    candidate.underlying = "SPY"
    candidate.spread_type = "iron_condor"
    candidate.expiry = "2026-04-01"
    candidate.contracts = 1
    executor.execute_iron_condor(candidate, dry_run=True)
    assert len(broker.orders_placed) == 0
```

- [ ] **Step 4: Write manager test**

Create `tests/test_manager.py`:

```python
from nodeble.strategy.manager import evaluate_positions, verify_pending_fills, cleanup_stale_orders
from nodeble.core.state import SpreadState


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
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_executor.py tests/test_manager.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/nodeble/strategy/executor.py src/nodeble/strategy/manager.py tests/test_executor.py tests/test_manager.py
git commit -m "feat: extract executor and manager with dry-run tests"
```

---

### Task 9: Strategy factory

**Files:**
- Create: `src/nodeble/strategy/factory.py` (from `reference/tiger-trading/condor/factory.py`)
- Create: `tests/test_factory.py`

- [ ] **Step 1: Extract `factory.py`**

Copy `reference/tiger-trading/condor/factory.py` → `src/nodeble/strategy/factory.py`.

Fix imports:
```python
from options.state import SpreadState
from options import risk as options_risk
from options.strike_selector import (
    get_spread_width, select_put_spread_strikes,
    select_call_spread_strikes, build_candidate, SpreadCandidate,
)
from options.chain_screener import (
    screen_symbol_iv, is_earnings_blackout,
    select_best_expiry, fetch_chain_and_price,
)
from data.chain_recorder import record_chain_snapshot
```
→
```python
from nodeble.core.state import SpreadState
from nodeble.core import risk as options_risk
from nodeble.strategy.strike_selector import (
    get_spread_width, select_put_spread_strikes,
    select_call_spread_strikes, build_candidate, SpreadCandidate,
)
from nodeble.strategy.chain_screener import (
    screen_symbol_iv, is_earnings_blackout,
    select_best_expiry, fetch_chain_and_price,
)
from nodeble.data.chain_recorder import record_chain_snapshot
```

Also fix lazy imports inside the function body. Search for:
- `from data.vix import get_vix, apply_vix_overrides` → `from nodeble.data.vix import get_vix, apply_vix_overrides`
- `from options.chain_screener import compute_iv_rv_ratios` → `from nodeble.strategy.chain_screener import compute_iv_rv_ratios`
- `from options.chain_screener import check_cooldown` → `from nodeble.strategy.chain_screener import check_cooldown`

Fix the hardcoded config path `"config_condor/strategy.yaml"` in `load_strategy_config()` to accept a path parameter.

- [ ] **Step 2: Write factory test**

Create `tests/test_factory.py`:

```python
from unittest.mock import patch, MagicMock

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
    """Risk config is a FLAT dict — matches how load_risk_config() returns it."""
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
    """Symbol with IV rank below threshold is rejected."""
    broker = MockBroker()
    # Mock get_option_analysis to return low IV rank
    mock_analysis = MagicMock()
    mock_analysis.symbol = "SPY"
    mock_iv = MagicMock()
    mock_iv.rank = 0.10  # Below 0.30 threshold
    mock_analysis.iv_metric = mock_iv
    broker._option_analyses = [mock_analysis]

    state = SpreadState()
    candidates, rejections = scan_for_condors(
        broker=broker, state=state, risk_cfg=_make_risk_cfg(),
        strategy_cfg=_make_strategy_cfg(), dry_run=True,
    )
    assert candidates == []
    assert len(rejections) > 0
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/test_factory.py -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add src/nodeble/strategy/factory.py tests/test_factory.py
git commit -m "feat: extract iron condor factory"
```

---

### Task 10: CLI entry point

**Files:**
- Create: `src/nodeble/__main__.py`

- [ ] **Step 1: Write `__main__.py`**

This is a REWRITE of `reference/tiger-trading/run_condor_job.py`, not a copy. Remove all cross-strategy awareness (theta, stocks, portfolio_risk, trade_journal). Keep the same CLI interface.

```python
"""NODEBLE CLI — Iron Condor trading automation.

Usage:
    python -m nodeble --mode scan [--dry-run] [--force]
    python -m nodeble --mode manage [--dry-run] [--force]
    python -m nodeble --test-broker
    python -m nodeble --validate-config
"""
import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from nodeble.paths import get_data_dir, get_config_dir
from nodeble.core.state import SpreadState
from nodeble.core import risk as options_risk
from nodeble.core.audit import log_event
from nodeble.core.calendar import is_market_open
from nodeble.strategy.factory import scan_for_condors
from nodeble.strategy.executor import SpreadExecutor
from nodeble.strategy.manager import (
    cleanup_stale_orders, verify_pending_fills, evaluate_positions,
)

logger = logging.getLogger("nodeble")
NY = ZoneInfo("America/New_York")


def setup_logging():
    log_dir = get_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_dir / "nodeble.log"),
        ],
    )


def load_config(name: str) -> dict:
    path = get_config_dir() / name
    if not path.exists():
        logger.error(f"Config not found: {path}")
        sys.exit(1)
    return yaml.safe_load(path.read_text())


def load_broker():
    """Lazy-load TigerBroker to avoid importing tigeropen at module level."""
    try:
        from nodeble.core.tiger_broker import TigerBroker
        broker_cfg = load_config("broker.yaml")
        return TigerBroker(broker_cfg)
    except Exception as e:
        logger.error(f"Failed to initialize broker: {e}")
        return None


def load_notifier():
    try:
        from nodeble.notify.telegram import TelegramNotifier
        notify_cfg = load_config("notify.yaml")
        return TelegramNotifier(notify_cfg)
    except Exception:
        logger.warning("Telegram notifier not configured, running without notifications")
        return None


def test_broker():
    """Test broker connection and display account info."""
    broker = load_broker()
    if broker is None:
        print("FAIL: Could not connect to broker")
        sys.exit(1)
    try:
        assets = broker.get_assets()
        seg = assets.segments["S"]
        print(f"OK: Connected to Tiger Brokers")
        print(f"  Cash available: ${seg.cash_available_for_trade:,.2f}")
        print(f"  Net liquidation: ${seg.net_liquidation:,.2f}")
    except Exception as e:
        print(f"FAIL: {e}")
        sys.exit(1)


def run_scan(broker, notifier, state, state_path, risk_cfg, strategy_cfg, dry_run):
    # Risk gate
    if not options_risk.check_kill_switch(risk_cfg):
        logger.warning("Kill switch is ON — aborting scan")
        return []

    candidates, rejections = scan_for_condors(
        broker=broker, state=state, risk_cfg=risk_cfg,
        strategy_cfg=strategy_cfg, dry_run=dry_run,
    )

    if not candidates:
        logger.info(f"No candidates found ({len(rejections)} rejections)")
        return []

    executor = SpreadExecutor(
        broker=broker, notifier=notifier, config=strategy_cfg,
        state=state, state_path=state_path,
    )

    results = []
    for candidate in candidates:
        # Per-candidate risk checks
        if not options_risk.check_max_spreads(state, risk_cfg):
            break
        if not options_risk.check_total_exposure(state, risk_cfg, candidate.max_risk * candidate.contracts * 100):
            continue

        result = executor.execute_iron_condor(candidate, dry_run=dry_run)
        results.append(result)
        log_event("condor_execution", result)

    return results


def run_manage(broker, notifier, state, state_path, risk_cfg, strategy_cfg, dry_run):
    cleanup_stale_orders(broker=broker, state=state)
    verify_pending_fills(broker=broker, state=state)

    actions = evaluate_positions(
        state=state, broker=broker,
        strategy_cfg=strategy_cfg,
    )

    if not actions:
        logger.info("No management actions needed")
        return []

    executor = SpreadExecutor(
        broker=broker, notifier=notifier, config=strategy_cfg,
        state=state, state_path=state_path,
    )

    results = []
    for action in actions:
        result = executor.close_spread(action.position, dry_run=dry_run)
        results.append(result)
        log_event("condor_close", result)

    return results


def main():
    parser = argparse.ArgumentParser(description="NODEBLE Iron Condor Automation")
    parser.add_argument("--mode", choices=["scan", "manage"], help="Run mode")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without placing orders")
    parser.add_argument("--force", action="store_true", help="Bypass dedup guard")
    parser.add_argument("--test-broker", action="store_true", help="Test broker connection")
    parser.add_argument("--validate-config", action="store_true", help="Validate config files")
    args = parser.parse_args()

    setup_logging()

    if args.test_broker:
        test_broker()
        return

    if not args.mode:
        parser.print_help()
        sys.exit(1)

    # Load configs
    risk_cfg = options_risk.load_risk_config(str(get_config_dir() / "risk.yaml"))
    strategy_cfg = load_config("strategy.yaml")

    # Force dry-run if config says so
    dry_run = args.dry_run
    if strategy_cfg.get("mode") == "dry_run":
        dry_run = True

    # Load state
    data_dir = get_data_dir() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    state_path = str(data_dir / "state.json")
    state = SpreadState.load(state_path)

    # Dedup guard
    today = date.today().isoformat()
    if args.mode == "scan" and state.last_scan_date == today and not args.force:
        logger.info("Already scanned today. Use --force to override.")
        return
    if args.mode == "manage" and state.last_manage_date == today and not args.force:
        logger.info("Already managed today. Use --force to override.")
        return

    # Market hours advisory
    if not is_market_open():
        logger.info("Market is closed (advisory — proceeding anyway for scan)")

    # Init broker + notifier
    broker = None if dry_run else load_broker()
    notifier = load_notifier()

    # Run
    if args.mode == "scan":
        results = run_scan(broker, notifier, state, state_path, risk_cfg, strategy_cfg, dry_run)
        if not dry_run:
            state.last_scan_date = today
            state.save(state_path)
    else:
        results = run_manage(broker, notifier, state, state_path, risk_cfg, strategy_cfg, dry_run)
        if not dry_run:
            state.last_manage_date = today
            state.save(state_path)

    # Save signals/executions
    signals_dir = data_dir / "signals"
    signals_dir.mkdir(exist_ok=True)
    exec_dir = data_dir / "executions"
    exec_dir.mkdir(exist_ok=True)
    out_dir = signals_dir if args.mode == "scan" else exec_dir
    out_path = out_dir / f"{args.mode}_{today}.json"
    out_path.write_text(json.dumps(results, default=str, indent=2))

    # Summary
    print(f"\n{'='*40}")
    print(f"Mode: {args.mode} | Dry-run: {dry_run}")
    print(f"Results: {len(results)} actions")
    print(f"Open positions: {len(state.get_open_positions())}")
    print(f"{'='*40}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write CLI test**

Create `tests/test_main.py`:

```python
import subprocess
import sys


def test_cli_help():
    result = subprocess.run(
        [sys.executable, "-m", "nodeble", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "scan" in result.stdout
    assert "manage" in result.stdout
    assert "dry-run" in result.stdout
```

- [ ] **Step 3: Run test**

```bash
uv run pytest tests/test_main.py -v
```

Expected: pass.

- [ ] **Step 4: Commit**

```bash
git add src/nodeble/__main__.py tests/test_main.py
git commit -m "feat: add CLI entry point — python -m nodeble"
```

---

### Task 11: TigerBroker implementation

**Files:**
- Create: `src/nodeble/core/tiger_broker.py` (from `reference/tiger-trading/src/broker.py`)

- [ ] **Step 1: Extract broker**

Copy `reference/tiger-trading/src/broker.py` → `src/nodeble/core/tiger_broker.py`.

No internal import changes needed (only `logging`, `sys`, `pathlib`, `typing`, `yaml`, and lazy `tigeropen` imports).

Fix the config path. Find the default `"config/tiger.yaml"` and remove it — the constructor should require config to be passed as a parameter (dict), not read from a file:

```python
class TigerBroker:
    def __init__(self, config: dict):
        self._config = config
        self._trade_client = None
        self._quote_client = None
        # ... rest of lazy init
```

The caller (`__main__.py`) handles loading `broker.yaml` and passing the dict.

- [ ] **Step 2: Smoke test (import only, no broker connection)**

```bash
uv run python -c "from nodeble.core.tiger_broker import TigerBroker; print('OK')"
```

Expected: `OK` (tigeropen must be installed, but no connection needed)

- [ ] **Step 3: Commit**

```bash
git add src/nodeble/core/tiger_broker.py
git commit -m "feat: extract TigerBroker implementation"
```

---

### Task 12: Port tests from tiger-trading

**Files:**
- Create: `tests/test_spread_guards.py` (from `reference/tiger-trading/tests/test_spread_guards.py`)
- Update: `tests/test_factory.py` (merge tests from `reference/tiger-trading/tests/test_condor_factory.py`)
- Update: `tests/test_executor.py` (merge tests from `reference/tiger-trading/tests/test_options_executor.py`)
- Update: `tests/test_manager.py` (merge tests from `reference/tiger-trading/tests/test_options_manager.py`)

- [ ] **Step 1: Port test_spread_guards.py**

Copy `reference/tiger-trading/tests/test_spread_guards.py` → `tests/test_spread_guards.py`.

Fix all imports using the import rewrite rule:
- `from options.executor import SpreadExecutor` → `from nodeble.strategy.executor import SpreadExecutor`
- `from options.state import ...` → `from nodeble.core.state import ...`
- `from options.strike_selector import ...` → `from nodeble.strategy.strike_selector import ...`
- `from options import risk` → `from nodeble.core import risk`

- [ ] **Step 2: Port remaining factory tests**

Copy test functions from `reference/tiger-trading/tests/test_condor_factory.py` into `tests/test_factory.py`. Fix imports per the rewrite rule. Also fix any `@patch` decorators to use new module paths:
- `@patch("condor.factory.is_earnings_blackout")` → `@patch("nodeble.strategy.factory.is_earnings_blackout")`
- etc.

- [ ] **Step 3: Port remaining executor tests**

Copy test functions from `reference/tiger-trading/tests/test_options_executor.py` into `tests/test_executor.py`. Fix imports per rewrite rule.

- [ ] **Step 4: Port remaining manager tests**

Copy test functions from `reference/tiger-trading/tests/test_options_manager.py` into `tests/test_manager.py`. Fix imports per rewrite rule.

- [ ] **Step 5: Port test_condor_job.py into test_main.py**

Copy test functions from `reference/tiger-trading/tests/test_condor_job.py` (173 lines) into `tests/test_main.py`. Fix imports:
- `from run_condor_job import ...` → `from nodeble.__main__ import ...`
- Apply standard import rewrite rule for options/condor/engine references.
- Note: risk_cfg in these tests uses FLAT dicts (no `"risk"` wrapper).

- [ ] **Step 6: Run all tests**

```bash
uv run pytest tests/ -v --tb=short
```

Expected: all tests pass. If any fail due to import issues or API changes, fix them.

- [ ] **Step 7: Commit**

```bash
git add tests/
git commit -m "feat: port IC tests from tiger-trading (~1,969 lines)"
```

---

### Task 13: Dry-run safety tests

**Files:**
- Create: `tests/test_dry_run_safety.py`

- [ ] **Step 1: Write two-layer dry-run safety tests**

```python
"""Prove that dry-run mode CANNOT place real orders.

Two independent safety layers:
1. MockBroker — test double that records but never sends orders
2. Executor dry_run flag — skips order placement entirely
"""
from nodeble.strategy.executor import SpreadExecutor
from nodeble.strategy.factory import scan_for_condors
from nodeble.core.state import SpreadState
from nodeble.strategy.strike_selector import SpreadCandidate
from mock_broker import MockBroker


def _make_candidate():
    c = SpreadCandidate()
    c.underlying = "SPY"
    c.spread_type = "iron_condor"
    c.expiry = "2026-04-01"
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
    # MockBroker has no network code — this is provable by inspection
    assert broker.get_order(oid).status == "FILLED"


def test_close_spread_dry_run(tmp_path):
    """Closing in dry-run also places zero orders."""
    from nodeble.core.state import SpreadPosition, SpreadLeg
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
```

- [ ] **Step 2: Run dry-run safety tests**

```bash
uv run pytest tests/test_dry_run_safety.py -v
```

Expected: all 3 tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_dry_run_safety.py
git commit -m "test: add two-layer dry-run safety tests"
```

---

### Task 14: Config templates

**Files:**
- Create: `config/strategy.yaml.example`
- Create: `config/strategy-moderate.yaml.example`
- Create: `config/strategy-aggressive.yaml.example`
- Create: `config/risk.yaml.example`
- Create: `config/broker.yaml.example`
- Create: `config/notify.yaml.example`

- [ ] **Step 1: Create conservative strategy template**

Create `config/strategy.yaml.example`:

```yaml
# NODEBLE Iron Condor Strategy — Conservative Template
# Designed for accounts $20-50K. Lower risk, fewer trades.

mode: dry_run  # Change to "live" after pre-flight checklist passes

watchlist:
  - SPY
  - QQQ
  - IWM

selection:
  min_iv_rank: 0.35
  min_iv_rv_ratio: 0
  put_delta_min: 0.08
  put_delta_max: 0.15
  call_delta_min: 0.08
  call_delta_max: 0.15
  min_open_interest: 100
  max_spread_pct: 0.10
  min_credit_pct: 0.25
  dte_min: 30
  dte_max: 45
  dte_ideal: 35
  prefer_monthly: true
  earnings_blackout_days: 10
  cooldown_days: 5
  max_new_positions_per_run: 1
  price_guard_pct: 0.03

management:
  max_risk_per_trade: 2000
  profit_take_pct: 0.50
  stop_loss_pct: 2.0
  close_before_dte: 3

execution:
  allow_degradation: false
  fill_timeout_sec: 30

sizing:
  spread_width_rules:
    - {max_price: 200, width: 5}
    - {max_price: 500, width: 10}
    - {max_price: 999999, width: 15}
```

- [ ] **Step 2: Create moderate and aggressive templates**

Create `config/strategy-moderate.yaml.example` — same structure with looser parameters:
- `min_iv_rank: 0.30`, wider delta range (`0.10-0.20`), `dte_ideal: 30`, `max_risk_per_trade: 3500`, `max_new_positions_per_run: 2`, `cooldown_days: 3`

Create `config/strategy-aggressive.yaml.example`:
- `min_iv_rank: 0.25`, wider delta (`0.10-0.25`), `dte_ideal: 25`, `max_risk_per_trade: 5000`, `max_new_positions_per_run: 3`, `cooldown_days: 0`

- [ ] **Step 3: Create risk template**

Create `config/risk.yaml.example`:

```yaml
# NODEBLE Risk Controls
# All safety gates are fail-closed: any error = don't trade

risk:
  kill_switch: false
  min_cash_floor: 20000
  max_concurrent_spreads: 8
  max_spreads_per_symbol: 2
  max_daily_orders: 10
  max_daily_loss: 1500
  max_total_exposure: 20000
  max_portfolio_delta: 200
  circuit_breaker:
    enabled: true
```

- [ ] **Step 4: Create broker and notify templates**

Create `config/broker.yaml.example`:

```yaml
# Tiger Brokers API credentials
# Keep this file secure — chmod 600

tiger_id: "YOUR_TIGER_ID"
account: "YOUR_ACCOUNT_NUMBER"
private_key_path: "~/.nodeble/config/tiger_private_key.pem"
sandbox: false
language: "en_US"
```

Create `config/notify.yaml.example`:

```yaml
# Telegram notification settings

telegram:
  bot_token: "YOUR_BOT_TOKEN"
  chat_id: "YOUR_CHAT_ID"
  enabled: true
```

- [ ] **Step 5: Commit**

```bash
git add config/
git commit -m "feat: add strategy, risk, broker, and notify config templates"
```

---

### Task 15: Deploy script + systemd

**Files:**
- Create: `deploy/deploy.sh`
- Create: `deploy/update.sh`
- Create: `deploy/nodeble.service`
- Create: `deploy/nodeble-scan.cron`
- Create: `deploy/nodeble-manage.cron`

- [ ] **Step 1: Create systemd service file**

Create `deploy/nodeble.service`:

```ini
[Unit]
Description=NODEBLE Iron Condor Bot
After=network.target

[Service]
Type=oneshot
User=%i
WorkingDirectory=/home/%i/nodeble
ExecStart=/home/%i/nodeble/.venv/bin/python -m nodeble --mode scan
Environment=PYTHONPATH=/home/%i/nodeble/src

[Install]
WantedBy=multi-user.target
```

Note: for Phase 1, cron is used for scheduling (not systemd timer). The service file is available for manual runs.

- [ ] **Step 2: Create cron templates**

Create `deploy/nodeble-scan.cron`:
```
# Scan for iron condor candidates — weekdays 10:00 AM ET
# Adjust time based on your VPS timezone
0 10 * * 1-5 cd /home/$USER/nodeble && .venv/bin/python -m nodeble --mode scan >> ~/.nodeble/logs/cron.log 2>&1
```

Create `deploy/nodeble-manage.cron`:
```
# Manage open positions — weekdays 10:30 AM and 3:00 PM ET
30 10 * * 1-5 cd /home/$USER/nodeble && .venv/bin/python -m nodeble --mode manage >> ~/.nodeble/logs/cron.log 2>&1
0 15 * * 1-5 cd /home/$USER/nodeble && .venv/bin/python -m nodeble --mode manage >> ~/.nodeble/logs/cron.log 2>&1
```

- [ ] **Step 3: Create deploy.sh**

Create `deploy/deploy.sh` — the guided deployment script. Must handle:
1. Check Python 3.12+ (install via apt if missing)
2. Install uv if missing
3. Clone/pull repo
4. Create venv + install deps
5. Create `~/.nodeble/` directory structure
6. Interactive prompts for credentials (Tiger, Telegram)
7. Write config files from templates
8. Run `python -m nodeble --test-broker`
9. Install cron jobs
10. Run first dry-run scan
11. Print success message

The script should be idempotent (safe to re-run).

- [ ] **Step 4: Create update.sh**

Create `deploy/update.sh`:

```bash
#!/bin/bash
set -e

echo "Updating NODEBLE..."

cd "$(dirname "$0")/.."

# Pull latest code
git pull --ff-only

# Reinstall deps (in case they changed)
uv pip install -e ".[dev]"

# Run a dry-run scan to verify nothing is broken
echo "Running verification scan (dry-run)..."
.venv/bin/python -m nodeble --mode scan --dry-run --force

echo "Update complete. Cron jobs will use the new code on next run."
```

- [ ] **Step 5: Commit**

```bash
git add deploy/
git commit -m "feat: add deploy script, systemd service, and cron templates"
```

---

### Task 16: Integration smoke test

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write end-to-end dry-run test**

```python
"""End-to-end integration test: scan + manage cycle with MockBroker.

Verifies the full pipeline works without a real broker.
"""
import tempfile
from pathlib import Path

from nodeble.core.state import SpreadState
from nodeble.core import risk as options_risk
from nodeble.strategy.factory import scan_for_condors
from nodeble.strategy.executor import SpreadExecutor
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
    """Scan cycle completes without errors in dry-run mode."""
    broker = MockBroker()
    state = SpreadState()
    strategy_cfg, risk_cfg = _make_cfgs()

    candidates, rejections = scan_for_condors(
        broker=broker, state=state,
        risk_cfg=risk_cfg, strategy_cfg=strategy_cfg,
        dry_run=True,
    )
    # With MockBroker returning no IV data, expect 0 candidates
    assert isinstance(candidates, list)
    assert isinstance(rejections, list)


def test_manage_cycle_no_positions():
    """Manage cycle completes cleanly with no open positions."""
    broker = MockBroker()
    state = SpreadState()
    strategy_cfg, risk_cfg = _make_cfgs()

    actions = evaluate_positions(
        state=state, broker=broker,
        strategy_cfg=strategy_cfg,
    )
    assert actions == []


def test_state_roundtrip(tmp_path):
    """State can be saved and loaded through a full cycle."""
    state_path = str(tmp_path / "state.json")
    state = SpreadState()
    state.last_scan_date = "2026-03-20"
    state.save(state_path)

    loaded = SpreadState.load(state_path)
    assert loaded.last_scan_date == "2026-03-20"
    assert len(loaded.positions) == 0
```

- [ ] **Step 2: Run all tests**

```bash
uv run pytest tests/ -v --tb=short
```

Expected: ALL tests pass. This is the final verification before deployment.

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add end-to-end integration smoke test"
```

---

### Task 17: Final verification + README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Run full test suite with coverage**

```bash
uv run pytest tests/ -v --cov=nodeble --cov-report=term-missing
```

Expected: all tests pass, reasonable coverage on core modules.

- [ ] **Step 2: Verify CLI works**

```bash
uv run python -m nodeble --help
```

Expected: help text with scan, manage, --dry-run, --test-broker options.

- [ ] **Step 3: Write README**

Create `README.md` with:
- What NODEBLE is (1 paragraph)
- Quick start for development (`uv venv && uv pip install -e ".[dev]"`)
- How to deploy for a friend (`bash deploy/deploy.sh`)
- CLI usage examples
- Config file locations
- Pre-flight checklist reference (link to plan/06)

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: add README with setup and deployment instructions"
```
