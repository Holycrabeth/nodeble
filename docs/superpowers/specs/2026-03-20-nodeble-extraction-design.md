# NODEBLE Phase 1 Extraction Design

## Goal

Extract the Iron Condor factory from `reference/tiger-trading` into a standalone `nodeble` Python package that a friend can deploy on their own Vultr VPS via `deploy.sh`.

## Extraction Spike Results

- **GO for extraction** — clean acyclic dependency graph, no circular imports, no global state
- Primary changes: import paths + config path constants
- Some modules need additional work (see Module Mapping for details)
- External deps: tigeropen, pyyaml, yfinance, pandas, numpy, pyarrow, pandas_market_calendars

## Divergences from Architecture Draft

- **Flatter project structure** — `src/nodeble/strategy/` instead of `backend/core/strategies/iron_condor/`. Phase 1 has one strategy; the deeper nesting is for multi-strategy Phase 2+.
- **JSON state, not SQLite** — matches tiger-trading; SQLite upgrade deferred to Phase 2 per Session 4 plan.
- **No Docker** — `deploy.sh` on bare Ubuntu is simpler for the target user. Docker deferred.
- **No `data/earnings.py`** — earnings blackout is inline in `chain_screener.py` (yfinance call). The Architecture Draft lists it separately but the source code doesn't use a separate module.

## Project Structure

```
nodeble/
├── pyproject.toml                    # Package config (uv)
├── README.md                         # Setup instructions
├── deploy/
│   ├── deploy.sh                     # Guided deployment script
│   ├── update.sh                     # Pull + restart
│   └── nodeble.service               # systemd unit file
├── config/
│   ├── strategy.yaml.example         # IC strategy template (Conservative)
│   ├── strategy-moderate.yaml.example
│   ├── strategy-aggressive.yaml.example
│   ├── risk.yaml.example             # Risk limits template
│   └── broker.yaml.example           # Tiger credentials template
├── src/
│   └── nodeble/
│       ├── __init__.py
│       ├── __main__.py               # CLI entry: python -m nodeble --mode scan|manage
│       ├── core/
│       │   ├── __init__.py
│       │   ├── broker.py             # BrokerAdapter protocol + TigerBroker
│       │   ├── state.py              # SpreadState, SpreadPosition, SpreadLeg
│       │   ├── state_lock.py         # fcntl file locking
│       │   ├── risk.py               # 8-check fail-closed risk pipeline
│       │   ├── audit.py              # Append-only event logger
│       │   └── calendar.py           # is_market_open() utility
│       ├── strategy/
│       │   ├── __init__.py
│       │   ├── factory.py            # scan_for_condors()
│       │   ├── executor.py           # SpreadExecutor (sequential leg execution)
│       │   ├── manager.py            # evaluate_positions(), cleanup, verify fills
│       │   ├── strike_selector.py    # Strike selection + candidate building
│       │   └── chain_screener.py     # IV screening, earnings blackout, expiry selection
│       ├── data/
│       │   ├── __init__.py
│       │   ├── fetcher.py            # OHLCV data (Tiger API + yfinance fallback)
│       │   ├── cache.py              # Parquet cache
│       │   ├── vix.py                # VIX scaling (optional)
│       │   └── chain_recorder.py     # Option chain snapshots for audit
│       ├── engine/
│       │   ├── __init__.py
│       │   ├── circuit_breaker.py    # Intraday drawdown monitor
│       │   └── kill_switch.py        # Emergency order cancellation
│       └── notify/
│           ├── __init__.py
│           └── telegram.py           # Telegram notifier
└── tests/
    ├── conftest.py
    ├── test_factory.py
    ├── test_executor.py
    ├── test_manager.py
    ├── test_risk.py
    ├── test_state.py
    ├── test_strike_selector.py
    └── test_spread_guards.py
```

## Module Mapping (tiger-trading -> nodeble)

| tiger-trading | nodeble | Changes |
|---------------|---------|---------|
| `run_condor_job.py` | `src/nodeble/__main__.py` | Rewrite as clean CLI entry point. Remove theta/options cross-strategy awareness. Replace `check_portfolio_limits()` call with single-strategy exposure check (already in `risk.py`). Replace `log_trade()` call with `audit.log_event()`. |
| `run_execution_job.py` (partial) | `src/nodeble/core/calendar.py` | Extract only `is_market_open()` function (~20 lines). Uses `pandas_market_calendars` + `zoneinfo`. |
| `condor/factory.py` | `src/nodeble/strategy/factory.py` | Import path changes only. |
| `options/executor.py` | `src/nodeble/strategy/executor.py` | Import path changes only. |
| `options/manager.py` | `src/nodeble/strategy/manager.py` | Import path changes only. |
| `options/state.py` | `src/nodeble/core/state.py` | Import path changes only. |
| `options/strike_selector.py` | `src/nodeble/strategy/strike_selector.py` | No changes (pure utility, zero imports). |
| `options/chain_screener.py` | `src/nodeble/strategy/chain_screener.py` | Import path changes (including lazy imports of `data.cache.DataCache` inside functions). |
| `options/risk.py` | `src/nodeble/core/risk.py` | Import path changes. Remove hardcoded config path, accept as parameter. |
| `src/broker.py` | `src/nodeble/core/broker.py` | Import path changes. Config path from `~/.nodeble/config/broker.yaml`. |
| `engine/kill_switch.py` | `src/nodeble/engine/kill_switch.py` | Import path changes only. |
| `engine/circuit_breaker.py` | `src/nodeble/engine/circuit_breaker.py` | Fix `__file__`-relative path to use config-based data directory. |
| `engine/state_lock.py` | `src/nodeble/core/state_lock.py` | No changes (zero internal imports). |
| `engine/audit.py` | `src/nodeble/core/audit.py` | Import path changes only. |
| `data/fetcher.py` | `src/nodeble/data/fetcher.py` | Import path changes. Note: accepts `broker` parameter for Tiger API price fetching (not fully standalone). |
| `data/cache.py` | `src/nodeble/data/cache.py` | Fix hardcoded `data/cache` path to use config-based directory. |
| `data/vix.py` | `src/nodeble/data/vix.py` | No changes (standalone utility). |
| `data/chain_recorder.py` | `src/nodeble/data/chain_recorder.py` | Fix hardcoded path to config-based directory. |
| `src/notify.py` | `src/nodeble/notify/telegram.py` | Import path changes only. |

## Config & Data Paths

All user data lives under `~/.nodeble/`:

```
~/.nodeble/
├── config/
│   ├── strategy.yaml        # Copied from template during deploy.sh
│   ├── risk.yaml
│   ├── broker.yaml           # Tiger credentials (never committed to git)
│   └── notify.yaml           # Telegram bot token + chat ID
├── data/
│   ├── state.json            # Position state
│   ├── cache/                # Parquet price cache
│   ├── chain_snapshots/      # Option chain audit trail
│   ├── signals/              # Scan signal logs
│   ├── executions/           # Execution logs
│   ├── audit/                # Event audit trail
│   └── circuit_breaker.json  # Circuit breaker state
└── logs/
    └── nodeble.log           # Application log (rotated)
```

## Key Design Decisions

1. **`~/.nodeble/` for all user data** — keeps code and data separate, survives git pull updates, `.gitignore`-friendly.

2. **`python -m nodeble` entry point** — replaces `run_condor_job.py`. Same CLI: `--mode scan|manage`, `--dry-run`, `--force`.

3. **BrokerAdapter protocol** — `TigerBroker` implements it. `MockBroker` for testing. Protocol defined in `broker.py` with the methods the executor/factory actually call.

4. **No portfolio_risk.py** — that module reads state files from ALL 6 strategies in tiger-trading. NODEBLE only has IC. Defer cross-strategy risk to Phase 2+ when more strategies are added.

5. **No regime filter** — optional in tiger-trading, config-gated. Omit for Phase 1 to reduce scope. Can add later.

6. **No trade_journal.py** — telemetry module not needed for Phase 1. Audit log is sufficient.

7. **Strategy templates** — three YAML files (conservative/moderate/aggressive) with safe defaults. `deploy.sh` lets the friend pick one.

8. **Scheduling via cron** — Phase 1 uses two cron jobs: scan (weekdays 10:00 ET) and manage (weekdays 10:30 ET, 15:00 ET). Simpler than APScheduler for a systemd service. APScheduler deferred to Phase 2.

9. **Error handling rule** — carried from tiger-trading: "Advisory gates fail-open, safety gates fail-closed." Market hours = advisory (returns True on error). Daily loss / price guard = safety (blocks on error).

## BrokerAdapter Protocol

Methods the IC pipeline actually calls (the protocol contract for `MockBroker` and future brokers):

```python
class BrokerAdapter(Protocol):
    def get_option_analysis(self, symbols: list[str]) -> list: ...
    def get_stock_price(self, symbol: str) -> float: ...
    def get_option_expirations(self, symbol: str) -> list[dict]: ...
    def get_option_chain(self, symbol: str, expiry: str, option_filter: dict) -> list[dict]: ...
    def get_option_briefs(self, identifiers: list[str]) -> list: ...
    def place_option_market_order(self, identifier: str, action: str, quantity: int) -> int: ...
    def get_order(self, order_id: int) -> object: ...
    def cancel_order(self, order_id: int) -> None: ...
    def get_open_orders(self, sec_type: str = "OPT") -> list: ...
    def get_assets(self) -> object: ...  # .segments["S"].cash_available_for_trade, .net_liquidation
    def get_positions(self, sec_type: str = "OPT") -> list: ...
```

## What NOT to Extract

- `engine/portfolio_risk.py` (725 lines) — cross-strategy, not needed for IC-only
- `engine/regime.py` — optional regime filter, defer
- `journal/trade_journal.py` — telemetry, defer
- `run_execution_job.py` — only need `is_market_open()`, inline it
- `theta/`, `stocks/`, `pmcc/` — other strategies, not in scope
- `backtest_options/` — backtesting infra, defer (but port SnapshotBroker for tests)

## External Dependencies

```toml
[project]
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
```

## deploy.sh Behavior

```bash
#!/bin/bash
# 1. Check Python 3.12+ installed, offer to install via apt if missing
# 2. Clone repo (or git pull if exists)
# 3. Create venv, install deps via uv
# 4. Create ~/.nodeble/ directory structure (config/, data/, logs/)
# 5. Interactive prompts:
#    - Tiger ID, account number
#    - Private key: paste content or provide file path → saved to ~/.nodeble/config/tiger_private_key.pem (chmod 600)
#    - Telegram bot token + chat ID
#    - Strategy template: [1] Conservative [2] Moderate [3] Aggressive
# 6. Write config files from templates + user input
# 7. Test broker connection: python -m nodeble --test-broker
#    - Verifies Tiger API credentials work
#    - Shows account number + NLV for confirmation
#    - Aborts deploy if test fails
# 8. Install systemd service + cron jobs (scan/manage schedule)
# 9. Start in dry-run mode
# 10. Print: "Bot running in dry-run mode. Check Telegram for status."
```

## Testing Strategy

- Port ~1,969 lines of IC tests from tiger-trading with import path fixes
- Add `MockBroker` class (extract from `backtest_options/snapshot_broker.py`)
- Two-layer dry-run safety: MockBroker swap AND executor `dry_run` guard
- Explicit tests proving dry-run cannot place real orders
- Explicit tests proving rollback works on partial fills
- Target: all ported tests pass before any friend deployment

## Test File Mapping (tiger-trading -> nodeble)

| tiger-trading test | nodeble test |
|-------------------|--------------|
| `tests/test_condor_factory.py` (395 lines) | `tests/test_factory.py` |
| `tests/test_options_executor.py` (454 lines) | `tests/test_executor.py` |
| `tests/test_options_manager.py` (247 lines) | `tests/test_manager.py` |
| `tests/test_condor_job.py` (173 lines) | `tests/test_main.py` |
| `tests/test_spread_guards.py` (316 lines) | `tests/test_spread_guards.py` |
| `tests/test_options_state.py` | `tests/test_state.py` |
| `tests/test_options_risk.py` | `tests/test_risk.py` |
| `tests/test_options_strike_selector.py` | `tests/test_strike_selector.py` |
| `backtest_options/snapshot_broker.py` (150 lines) | `tests/mock_broker.py` |
