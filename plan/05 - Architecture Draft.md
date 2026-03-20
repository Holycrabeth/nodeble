# Architecture Draft — Detailed Technical Design

---

## System Overview

### Phase 1: Headless Deployment (Telegram Only)

```
┌─────────────────────────────────────────────────────────────────┐
│                    User's VPS (Ubuntu 24.04)                     │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                  Python Backend (systemd)                    │ │
│  │                  Runs as background service                  │ │
│  │                                                              │ │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐  │ │
│  │  │ Scheduler │ │ Strategy  │ │  Risk     │ │ Notifier  │  │ │
│  │  │ (APSched) │ │ Engine    │ │  Engine   │ │ (Telegram)│  │ │
│  │  └─────┬─────┘ └─────┬─────┘ └─────┬─────┘ └───────────┘  │ │
│  │        │              │              │                       │ │
│  │  ┌─────┴──────────────┴──────────────┴──────────────────┐   │ │
│  │  │                    Core Layer                         │   │ │
│  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐             │   │ │
│  │  │  │ Broker   │ │  State   │ │  Data    │             │   │ │
│  │  │  │ Adapter  │ │  Manager │ │ Provider │             │   │ │
│  │  │  │ (Tiger)  │ │  (JSON)  │ │          │             │   │ │
│  │  │  └──────────┘ └──────────┘ └──────────┘             │   │ │
│  │  └──────────────────────────────────────────────────────┘   │ │
│  │                                                              │ │
│  │  API keys stored locally: ~/.nodeble/credentials/            │ │
│  │  State stored locally: ~/.nodeble/data/state.json            │ │
│  └──────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Phase 2: Web Dashboard Deployment

```
┌─────────────────────────────────────────────────────────────────┐
│                    User's VPS (Ubuntu 24.04)                     │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │              Nginx (reverse proxy + static)                │  │
│  │    Static: React frontend    Proxy: /api/* → :8721         │  │
│  └──────────────────────┬─────────────────────────────────────┘  │
│                         │ HTTP localhost:8721                     │
│  ┌──────────────────────┴─────────────────────────────────────┐  │
│  │                  Python Backend (FastAPI)                    │  │
│  │                  (same core as Phase 1)                     │  │
│  │  + API Routes (dashboard, strategy, risk, broker, settings) │  │
│  │  + Scheduler, Strategy Engine, Risk Engine, Notifier        │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  API keys stored locally: ~/.nodeble/credentials/                 │
│  Database stored locally: ~/.nodeble/data/nodeble.db              │
└───────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
nodeble/
├── backend/                          # Python (FastAPI + trading engine)
│   ├── pyproject.toml
│   ├── main.py                       # FastAPI app entry point
│   │
│   ├── api/                          # HTTP API routes
│   │   ├── __init__.py
│   │   ├── dashboard.py              # GET /positions, /pnl, /activity
│   │   ├── strategy.py               # GET/PUT /strategy, /templates
│   │   ├── risk.py                   # GET/PUT /risk, POST /kill-switch
│   │   ├── broker.py                 # POST /broker/connect, /broker/test
│   │   ├── scheduler.py             # GET/PUT /scheduler, POST /scan-now, /manage-now
│   │   └── settings.py              # GET/PUT /settings (Telegram, language, etc.)
│   │
│   ├── core/                         # Trading engine (extracted from tiger-trading)
│   │   ├── __init__.py
│   │   ├── broker_interface.py       # Abstract BrokerAdapter protocol
│   │   ├── broker_tiger.py           # Tiger implementation (from src/broker.py)
│   │   ├── broker_mock.py            # Mock for dry-run / paper trading
│   │   │
│   │   ├── strategies/               # Strategy implementations
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # Strategy protocol (scan/manage/status)
│   │   │   ├── iron_condor/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── factory.py       # ← condor/factory.py (322 lines)
│   │   │   │   ├── executor.py      # ← options/executor.py (894 lines, IC subset)
│   │   │   │   ├── manager.py       # ← options/manager.py (294 lines)
│   │   │   │   └── scanner.py       # Wraps factory + chain_screener
│   │   │   ├── csp/                  # Future: Cash-Secured Put
│   │   │   ├── covered_call/         # Future: Covered Call
│   │   │   └── credit_spread/        # Future: Credit Spread
│   │   │
│   │   ├── risk/                     # Risk engine
│   │   │   ├── __init__.py
│   │   │   ├── engine.py            # Sequential risk check pipeline
│   │   │   ├── checks.py            # Individual checks (kill_switch, cash_floor, etc.)
│   │   │   ├── circuit_breaker.py   # ← engine/circuit_breaker.py
│   │   │   └── kill_switch.py       # ← engine/kill_switch.py
│   │   │
│   │   ├── data/                     # Market data layer
│   │   │   ├── __init__.py
│   │   │   ├── provider.py          # DataProvider (OHLCV, quotes)
│   │   │   ├── chain_screener.py    # ← options/chain_screener.py
│   │   │   ├── strike_selector.py   # ← options/strike_selector.py
│   │   │   ├── earnings.py          # ← data/earnings.py
│   │   │   └── vix.py               # ← data/vix.py
│   │   │
│   │   ├── state/                    # State management
│   │   │   ├── __init__.py
│   │   │   ├── models.py            # SQLAlchemy models (positions, trades, config)
│   │   │   ├── database.py          # SQLite connection, migrations
│   │   │   └── manager.py           # State read/write operations
│   │   │
│   │   └── notifications/
│   │       ├── __init__.py
│   │       ├── telegram.py          # Telegram notifier
│   │       └── notifier.py          # Notifier protocol (future: push, email)
│   │
│   ├── scheduler/
│   │   ├── __init__.py
│   │   └── jobs.py                  # APScheduler job definitions (scan, manage)
│   │
│   ├── templates/                    # Pre-built strategy templates (YAML)
│   │   ├── ic_conservative.yaml
│   │   ├── ic_moderate.yaml
│   │   ├── ic_aggressive.yaml
│   │   ├── csp_conservative.yaml    # Future
│   │   └── cc_weekly.yaml           # Future
│   │
│   └── tests/
│       ├── test_iron_condor.py
│       ├── test_risk_engine.py
│       ├── test_state.py
│       └── test_api.py
│
├── frontend/                         # React + TypeScript
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── src/
│   │   ├── main.tsx                  # Entry point
│   │   ├── App.tsx                   # Router + layout
│   │   ├── i18n/                     # Internationalisation
│   │   │   ├── en.json
│   │   │   └── zh.json
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx         # Main view — positions, P&L, activity
│   │   │   ├── StrategyConfig.tsx    # Template selector + parameter editor
│   │   │   ├── RiskControls.tsx      # Kill switch, limits, status
│   │   │   ├── BrokerSetup.tsx       # Credentials, connection test
│   │   │   ├── History.tsx           # Closed trades, P&L chart
│   │   │   └── Settings.tsx          # Telegram, language, scheduler
│   │   ├── components/
│   │   │   ├── PositionTable.tsx
│   │   │   ├── PnLChart.tsx
│   │   │   ├── KillSwitchButton.tsx
│   │   │   ├── StrategyCard.tsx
│   │   │   ├── ParameterSlider.tsx
│   │   │   ├── ActivityLog.tsx
│   │   │   └── StatusBadge.tsx
│   │   ├── hooks/
│   │   │   ├── useApi.ts            # Fetch wrapper for backend API
│   │   │   └── useWebSocket.ts      # Real-time updates (future)
│   │   └── lib/
│   │       ├── api.ts               # API client (typed)
│   │       └── types.ts             # Shared TypeScript types
│   └── index.html
│
├── deploy/                           # Deployment config
│   ├── nginx.conf                   # Nginx reverse proxy config (Phase 2)
│   ├── nodeble.service              # systemd unit file
│   └── deploy.sh                    # Guided deployment script
│
├── scripts/
│   ├── build.sh                     # Build frontend assets
│   ├── dev.sh                       # Dev mode (backend + frontend hot reload)
│   └── deploy-vultr.sh              # Headless deployment (VPS, no GUI)
│
└── docs/
    ├── quickstart-en.md
    └── quickstart-zh.md
```

---

## Code Extraction Map

What comes from tiger-trading → where it goes in nodeble:

| Source (tiger-trading) | Destination (nodeble) | Lines | Changes Needed |
|----------------------|---------------------|-------|----------------|
| `condor/factory.py` | `core/strategies/iron_condor/factory.py` | 322 | Import paths only |
| `options/executor.py` | `core/strategies/iron_condor/executor.py` | 894 | Extract IC methods, inject broker |
| `options/manager.py` | `core/strategies/iron_condor/manager.py` | 294 | Import paths only |
| `options/state.py` | `core/state/models.py` | 150 | Convert to SQLAlchemy models |
| `options/strike_selector.py` | `core/data/strike_selector.py` | 353 | No changes (pure logic) |
| `options/chain_screener.py` | `core/data/chain_screener.py` | 200 | Import paths only |
| `options/risk.py` | `core/risk/checks.py` | 150 | Conform to RiskCheck protocol |
| `src/broker.py` | `core/broker_tiger.py` | 641 | Extract interface to protocol |
| `engine/kill_switch.py` | `core/risk/kill_switch.py` | 110 | Import paths only |
| `engine/circuit_breaker.py` | `core/risk/circuit_breaker.py` | 143 | Import paths only |
| `engine/audit.py` | `core/state/audit.py` | 36 | No changes |
| `data/earnings.py` | `core/data/earnings.py` | 68 | No changes |
| `data/vix.py` | `core/data/vix.py` | 80 | No changes |
| `run_condor_job.py` | `scheduler/jobs.py` | 555 | Refactor to accept injected deps |
| **Total** | | **~3,996** | Mostly import path changes |

---

## Broker Adapter Interface

The core abstraction that makes multi-broker possible:

```python
# core/broker_interface.py

from typing import Protocol

class BrokerAdapter(Protocol):
    """Every broker plugin must implement this interface."""

    # ── Account ──
    def get_cash_available(self) -> float: ...
    def get_net_liquidation(self) -> float: ...
    def get_positions(self, sec_type: str = "OPT") -> list[dict]: ...

    # ── Market Data ──
    def get_stock_price(self, symbol: str) -> float: ...
    def get_option_expirations(self, symbol: str) -> list[str]: ...
    def get_option_chain(
        self, symbol: str, expiry: str, option_filter: dict | None = None
    ) -> list[dict]: ...
    def get_option_briefs(self, identifiers: list[str]) -> list[dict]: ...

    # ── Orders ──
    def place_option_order(
        self, identifier: str, action: str, quantity: int,
        limit_price: float, time_in_force: str = "DAY"
    ) -> str: ...  # returns order_id
    def get_order(self, order_id: str) -> dict: ...
    def cancel_order(self, order_id: str) -> bool: ...
    def get_open_orders(self, sec_type: str = "OPT") -> list[dict]: ...
```

**Implementations:**

| Class | File | Status |
|-------|------|--------|
| `TigerBroker` | `core/broker_tiger.py` | Extract from tiger-trading (641 lines) |
| `MockBroker` | `core/broker_mock.py` | Build for paper trading / dry-run |
| `IBKRBroker` | (future) | Extract from ibkr-sell-put |
| `LongportBroker` | (future) | Extract from longport-sell-put |
| `MoomooBroker` | (future) | Extract from moomoo-trading |

---

## Strategy Protocol

Every strategy follows the same lifecycle:

```python
# core/strategies/base.py

class Strategy(Protocol):
    """All strategies implement scan → execute → manage → status."""

    def scan(
        self, broker: BrokerAdapter, state: StateManager,
        risk: RiskEngine, config: dict
    ) -> list[Candidate]: ...
    """Find new opportunities. Returns candidates ranked by quality."""

    def execute(
        self, candidates: list[Candidate], broker: BrokerAdapter,
        state: StateManager, dry_run: bool = False
    ) -> list[Execution]: ...
    """Place orders for candidates. Returns execution results."""

    def manage(
        self, broker: BrokerAdapter, state: StateManager,
        risk: RiskEngine, config: dict
    ) -> list[Action]: ...
    """Manage open positions. Returns actions taken."""

    def status(
        self, state: StateManager, broker: BrokerAdapter | None = None
    ) -> StatusReport: ...
    """Current positions and P&L summary."""
```

---

## FastAPI Routes

```
Backend runs on localhost:8721 (only accessible from local machine)

── Dashboard ──
GET  /api/dashboard              → {positions, pnl_summary, recent_activity, risk_status}
GET  /api/positions              → [{spread_id, underlying, expiry, legs, pnl, status, ...}]
GET  /api/pnl                    → {total_credit, total_realized, unrealized, by_strategy}

── Strategy ──
GET  /api/templates              → [{name, description, risk_level, params}]
GET  /api/strategy               → {active_config}  (current running config)
PUT  /api/strategy               → update strategy config (validates before saving)
POST /api/strategy/validate      → dry-validate config without saving

── Risk ──
GET  /api/risk                   → {kill_switch, checks_status, circuit_breaker_level}
POST /api/risk/kill-switch       → {enabled: true/false}  toggle kill switch
GET  /api/risk/stress-test       → {scenarios: [{move, estimated_pnl}, ...]}

── Broker ──
POST /api/broker/connect         → {tiger_id, account, private_key_path} → test connection
GET  /api/broker/status          → {connected, account_id, nlv, cash}
POST /api/broker/test            → ping Tiger API, return latency + account info

── Scheduler ──
GET  /api/scheduler              → {jobs: [{name, next_run, last_run, status}]}
PUT  /api/scheduler              → update scan/manage times
POST /api/scheduler/scan-now     → trigger manual scan (returns immediately, runs async)
POST /api/scheduler/manage-now   → trigger manual manage

── Settings ──
GET  /api/settings               → {telegram, language, theme}
PUT  /api/settings               → update settings

── History ──
GET  /api/history/trades         → [{spread_id, entry_date, close_date, pnl, ...}]
GET  /api/history/pnl-chart      → [{date, cumulative_pnl}]  for charting

── System ──
GET  /api/health                 → {status, version, uptime, broker_connected}
GET  /api/logs                   → recent log entries (last 100 lines)
```

---

## Database Schema (SQLite)

Upgrading from JSON state files to SQLite for proper querying and history:

```sql
-- Strategy configurations (one active per strategy type)
CREATE TABLE strategy_config (
    id          INTEGER PRIMARY KEY,
    strategy    TEXT NOT NULL,          -- 'iron_condor', 'csp', 'covered_call'
    config_yaml TEXT NOT NULL,          -- full YAML config as text
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Open and historical positions
CREATE TABLE positions (
    id              INTEGER PRIMARY KEY,
    spread_id       TEXT UNIQUE NOT NULL,   -- 'SPY_iron_condor_2026-04-02_650_635_706_720'
    strategy        TEXT NOT NULL,
    underlying      TEXT NOT NULL,
    spread_type     TEXT NOT NULL,           -- 'iron_condor', 'bull_put', 'bear_call'
    expiry          TEXT NOT NULL,
    entry_date      TEXT NOT NULL,
    entry_credit    REAL NOT NULL,
    max_risk        REAL NOT NULL,
    contracts       INTEGER NOT NULL,
    status          TEXT NOT NULL,           -- 'pending','open','closed_profit','closed_stop','closed_dte','expired'
    close_date      TEXT,
    close_debit     REAL,
    realized_pnl    REAL DEFAULT 0,
    current_value   REAL,
    current_dte     INTEGER,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Individual legs of a spread
CREATE TABLE legs (
    id              INTEGER PRIMARY KEY,
    position_id     INTEGER NOT NULL REFERENCES positions(id),
    identifier      TEXT NOT NULL,           -- 'SPY   260402P00635000'
    strike          REAL NOT NULL,
    put_call        TEXT NOT NULL,           -- 'P' or 'C'
    action          TEXT NOT NULL,           -- 'BUY' or 'SELL'
    contracts       INTEGER NOT NULL,
    entry_premium   REAL NOT NULL,
    entry_delta     REAL,
    order_id        TEXT,
    status          TEXT NOT NULL DEFAULT 'pending'
);

-- Risk configuration
CREATE TABLE risk_config (
    id              INTEGER PRIMARY KEY,
    kill_switch     BOOLEAN DEFAULT FALSE,
    config_yaml     TEXT NOT NULL,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Audit trail (append-only)
CREATE TABLE audit_log (
    id          INTEGER PRIMARY KEY,
    timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    strategy    TEXT,
    event_type  TEXT NOT NULL,
    details     TEXT                         -- JSON blob
);

-- Broker credentials (encrypted at rest)
CREATE TABLE broker_config (
    id              INTEGER PRIMARY KEY,
    broker_type     TEXT NOT NULL,            -- 'tiger', 'ibkr', 'longport', 'moomoo'
    config_json     TEXT NOT NULL,            -- encrypted JSON
    is_active       BOOLEAN DEFAULT TRUE
);

-- Scheduler state
CREATE TABLE scheduler_state (
    id              INTEGER PRIMARY KEY,
    job_name        TEXT UNIQUE NOT NULL,
    last_run        TIMESTAMP,
    next_run        TIMESTAMP,
    last_status     TEXT,                    -- 'success', 'error', 'skipped'
    last_error      TEXT
);

-- Daily P&L snapshots (for history chart)
CREATE TABLE daily_pnl (
    id              INTEGER PRIMARY KEY,
    date            TEXT UNIQUE NOT NULL,
    total_credit    REAL,
    total_realized  REAL,
    unrealized      REAL,
    nlv             REAL,
    num_open        INTEGER
);
```

---

## Data Flow: Scan Cycle

```
1. Scheduler triggers scan job (e.g., 09:50 ET / 22:50 SGT)
   │
2. Risk pre-flight checks (fail-closed)
   ├── Kill switch off?
   ├── Circuit breaker green/yellow?
   ├── Cash floor met?
   ├── Max spreads not reached?
   └── Daily loss limit not breached?
   │
3. For each symbol in user's watchlist:
   ├── Fetch IV rank from Tiger API
   ├── Skip if IV rank < threshold (e.g., 0.30)
   ├── Check earnings blackout (7 days)
   ├── Check cooldown (no re-entry same symbol within X days)
   ├── Select best expiry (DTE 21-45, prefer monthly)
   ├── Fetch put chain → select put spread strikes (delta range)
   ├── Fetch call chain → select call spread strikes (delta range)
   ├── Build IC candidate (both wings required)
   └── Validate: credit ≥ min % of width
   │
4. For each candidate (ranked by credit/risk ratio):
   ├── Re-check: daily order limit, symbol limit, exposure limit, cash floor
   ├── Price guard: underlying moved >3% since scan start? → abort
   ├── Delta guard: short leg delta out of range? → abort
   ├── Execute 4 legs sequentially:
   │   ├── BUY long put → wait 30s for fill
   │   ├── SELL short put → wait 30s for fill
   │   ├── BUY long call → wait 30s for fill
   │   └── SELL short call → wait 30s for fill
   ├── If any leg fails → rollback all filled legs
   └── On success → save position to SQLite, log to audit
   │
5. Send Telegram notification: "Opened SPY IC 635/650-706/720 @ $3.77 credit"
   │
6. Update dashboard via API (frontend polls or WebSocket push)
```

---

## Data Flow: Manage Cycle

```
1. Scheduler triggers manage job (e.g., 09:40 ET / 22:40 SGT)
   │
2. Cleanup stale orders (pending > 4 hours → cancel)
   │
3. Verify pending fills
   ├── Check each pending leg: filled? → update status
   └── Phantom positions? → reconcile with broker
   │
4. Evaluate each open position:
   ├── Fetch live quotes (option briefs from Tiger)
   ├── Calculate current value (cost to close)
   ├── Profit target hit? (≥50% of max credit) → CLOSE
   ├── Stop loss hit? (≥200% of credit) → CLOSE
   ├── DTE ≤ 3? (gamma risk) → CLOSE
   ├── Expired? → mark expired, realise full credit
   └── Otherwise → HOLD
   │
5. Execute close actions:
   ├── 4 legs sequentially (reverse order: sell call → buy call → sell put → buy put)
   └── Save to SQLite, log to audit
   │
6. Send Telegram notification: "Closed SPY IC for $1.88 profit (50% target hit)"
   │
7. Update dashboard
```

---

## Frontend Pages (Detail)

### Dashboard (Main View)
```
┌──────────────────────────────────────────────────────────┐
│  NODEBLE   [Dashboard] [Strategy] [Risk] [History] [⚙]  │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─── Summary Cards ──────────────────────────────────┐ │
│  │ Open Positions: 4  │ Today's P&L: +$234           │ │
│  │ Total Credit: $1,847│ Realised P&L: $2,407         │ │
│  │ Unrealised: +$412   │ Risk Level: 🟢 Green         │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌─── Open Positions ────────────────────────────────┐  │
│  │ Symbol  Type  Expiry   DTE  Credit  Value   P&L   │  │
│  │ SPY     IC    Apr 02   14   $3.77   $2.53  +$372  │  │
│  │ QQQ     IC    Apr 02   14   $2.84   $2.10  +$222  │  │
│  │ AAPL    IC    Mar 27    8   $1.92   $0.95  +$291  │  │
│  │ MSFT    IC    Apr 10   22   $1.56   $1.40  + $48  │  │
│  └───────────────────────────────────────────────────┘  │
│                                                          │
│  ┌─── Activity Log ──────────────────────────────────┐  │
│  │ 22:50 — Scan: 2 candidates found, 1 executed       │  │
│  │ 22:40 — Manage: AAPL IC at 50% target → closing    │  │
│  │ 22:40 — Manage: SPY IC → hold (38% profit)         │  │
│  │ Yesterday — Closed IWM IC for +$188                 │  │
│  └───────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### Strategy Config Page
```
┌──────────────────────────────────────────────────────────┐
│  Strategy Configuration                                   │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─── Template ───────────────────────────────────────┐ │
│  │  [Conservative IC]  [Moderate IC]  [Aggressive IC] │ │
│  │   ✅ Selected         ○              ○              │ │
│  │                                                     │ │
│  │  "Wide wings, low delta, SPY/QQQ focus.            │ │
│  │   Targets ~12-15% annual return with minimal risk." │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌─── Watchlist (you choose) ─────────────────────────┐ │
│  │  [✅ SPY] [✅ QQQ] [☐ IWM] [☐ AAPL] [☐ MSFT]    │ │
│  │  [☐ NVDA] [☐ TSLA] [+ Add Symbol]                 │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌─── Parameters ─────────────────────────────────────┐ │
│  │  Put Delta:    ──●────── 0.10  (range: 0.05-0.25) │ │
│  │  Call Delta:   ──●────── 0.10  (range: 0.05-0.25) │ │
│  │  DTE:          ─────●─── 35    (range: 14-60)      │ │
│  │  Wing Width:   ──●────── $5    (range: $3-$20)     │ │
│  │  Min IV Rank:  ────●──── 0.30  (range: 0.10-0.60) │ │
│  │  Profit Target:─────●─── 50%   (range: 25%-75%)    │ │
│  │  Stop Loss:    ─────●─── 200%  (range: 100%-300%)  │ │
│  │  Max Condors:  ──●────── 3     (range: 1-10)       │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  [💾 Save]  [▶ Start]  [⏸ Pause]  [🧪 Paper Trade]     │
│                                                          │
│  ⚠ You are responsible for your own trading decisions.  │
│    This is a software tool, not financial advice.        │
└──────────────────────────────────────────────────────────┘
```

### Risk Controls Page
```
┌──────────────────────────────────────────────────────────┐
│  Risk Controls                                            │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─── KILL SWITCH ────────────────────────────────────┐ │
│  │                                                     │ │
│  │        [ 🔴  EMERGENCY STOP  ]                      │ │
│  │                                                     │ │
│  │   Status: INACTIVE (trading enabled)                │ │
│  │   Also available via Telegram: /kill                │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌─── Risk Limits ───────────────────────────────────┐  │
│  │  Cash Floor:      $20,000  (current: $85,400) ✅   │  │
│  │  Max Condors:     3        (current: 2)       ✅   │  │
│  │  Max Per Symbol:  2        (current: 1)       ✅   │  │
│  │  Max Daily Loss:  $2,000   (today: -$0)       ✅   │  │
│  │  Portfolio Delta:  150     (current: +42)      ✅   │  │
│  │  Circuit Breaker: GREEN    (0% drawdown)       ✅   │  │
│  └───────────────────────────────────────────────────┘  │
│                                                          │
│  ┌─── Stress Test ───────────────────────────────────┐  │
│  │  If SPY drops:                                     │  │
│  │   -5%:   Est. loss: -$340   (portfolio can handle) │  │
│  │  -10%:   Est. loss: -$890   (portfolio can handle) │  │
│  │  -20%:   Est. loss: -$1,620 (portfolio can handle) │  │
│  └───────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

---

## Web Deployment

### Phase 1: Headless (systemd + Telegram)

Phase 1 runs without any web frontend. The Python trading engine runs as a systemd service. Users interact exclusively via Telegram.

```bash
# deploy.sh handles all of this:
# 1. Install Python 3.12+, create venv, install deps
# 2. Prompt user for Tiger API credentials + Telegram token
# 3. User picks strategy template (numbered menu)
# 4. Create systemd service
# 5. Start in dry-run mode

sudo systemctl enable nodeble
sudo systemctl start nodeble

# Monitor via Telegram: /status, /kill, /kill off
# Update: bash update.sh (git pull + restart)
```

### Phase 2: Web Dashboard (Nginx + FastAPI + React)

Phase 2 adds a browser-based dashboard on top of the Phase 1 engine.

```
User's browser → Nginx (:80/:443)
                   ├── Static files: React frontend (built with Vite)
                   └── /api/* → FastAPI backend (:8721)
```

- Nginx serves React static files and reverse-proxies API requests to FastAPI
- FastAPI runs on localhost:8721 (not exposed directly to network)
- systemd manages the FastAPI process (auto-restart on crash)
- Updates: `git pull && npm run build && systemctl restart nodeble`

---

## Headless Mode (Vultr VPS)

For friends running on a VPS with no GUI:

```bash
# deploy-vultr.sh
# Sets up on a fresh Ubuntu 24.04 VPS

# Install Python
sudo apt install python3.12 python3.12-venv

# Clone and setup
git clone https://github.com/nodeble/nodeble.git
cd nodeble/backend
python3.12 -m venv ~/.nodeble/venv
source ~/.nodeble/venv/bin/activate
pip install -e .

# Configure
cp templates/ic_conservative.yaml ~/.nodeble/config/strategy.yaml
nano ~/.nodeble/config/strategy.yaml     # user edits watchlist + params
nano ~/.nodeble/config/broker.yaml       # Tiger API credentials
nano ~/.nodeble/config/notify.yaml       # Telegram bot token + chat ID

# Test connection
python -m backend.main --test-broker

# Start (headless, no GUI)
python -m backend.main --headless &

# Or via systemd for auto-restart
sudo cp scripts/nodeble.service /etc/systemd/system/
sudo systemctl enable nodeble
sudo systemctl start nodeble
```

In headless mode:
- FastAPI still runs (accessible via SSH tunnel if needed)
- Scheduler runs scan + manage at configured times
- All interaction via Telegram bot
- No web dashboard — CLI + Telegram only

---

## Security Model

```
Credentials:     ~/.nodeble/credentials/
                  ├── tiger_private_key.pem    (user's Tiger private key)
                  └── broker.yaml              (tiger_id, account — not sensitive)

Database:        ~/.nodeble/data/nodeble.db     (positions, trades, config)

Logs:            ~/.nodeble/logs/               (daily rotation)

Config:          ~/.nodeble/config/
                  ├── strategy.yaml
                  ├── risk.yaml
                  └── notify.yaml

All files:       chmod 700 ~/.nodeble/          (owner-only access)
API:             localhost:8721 only             (not exposed to network)
No cloud:        Everything local                (Phase 1-2)
```

---

## Open Technical Decisions

| Decision | Options | Recommendation | Status |
|----------|---------|---------------|--------|
| **Python bundling** | Require system Python vs embed vs PyInstaller | Require system Python + venv (simplest, Vultr-compatible) | Needs discussion |
| **Windows support** | Day 1 vs Mac-only first | Mac + Linux first (friends use Mac or Vultr Ubuntu) | Needs discussion |
| **Real-time updates** | Polling vs WebSocket | Polling every 5s for MVP, WebSocket later | Decided |
| **Strategy hot-reload** | Restart backend vs reload config | Reload config without restart (APScheduler supports this) | Decided |
| **Log format** | Text vs structured JSON | Structured JSON (easier to parse in frontend) | Decided |
| **Template updates** | Bundled with app vs remote fetch | Bundled (no phone-home, no server needed) | Decided |

---

**Status**: Detailed — ready for implementation planning
**Created**: 2026-03-19
**Related**: [[07 - Technology Stack]] | [[06 - MVP Definition]] | [[03 - Core IP & Reusable Components]]
