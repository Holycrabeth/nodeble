# Implementation Sessions

> A step-by-step guide broken into small sessions. Each session = one sitting (~1-3 hours), one topic, one deliverable. Designed for a non-developer founder using AI-assisted coding.

---

## Phase 1: Extract & Deploy for Friends (Sessions 1-12)

The goal: get the Iron Condor factory running on a Vultr VPS for one friend.

### Session 1: Understand the Codebase You're Extracting
- **What we do**: Walk through the iron condor factory code together. Understand what each file does, how they connect, what the data flows look like.
- **No coding.** Just reading and understanding.
- **Deliverable**: You can explain in your own words how a scan cycle works.

### Session 1.5: Extraction Spike
- **What we do**: Create a throwaway Python script outside tiger-trading. Try importing the IC factory modules (`condor.factory`, `options.executor`, `options.manager`, `options.state`, `options.risk`). Catalog every import failure, hidden dependency, and hardcoded path. Key risks: circular dependency via `run_execution_job.is_market_open()`, 13 direct `broker.*` calls in executor, `cwd = project root` assumptions.
- **Decision gate**: If extraction requires >20 hours beyond import paths, evaluate wrapping tiger-trading as a package instead.
- **Deliverable**: Dependency list with revised effort estimates. Go/no-go recommendation for extraction vs wrapping.

### Session 2: Set Up the New Project Repository
- **What we do**: Create a new git repo (`nodeble`), set up the folder structure, Python venv, `pyproject.toml`, basic dependencies.
- **Deliverable**: Empty project that runs `python -m nodeble` without errors.

### Session 3: Extract the Broker Adapter
- **What we do**: Copy `src/broker.py` from tiger-trading, create the `BrokerAdapter` protocol (interface), create `TigerBroker` implementation, create `MockBroker` for testing.
- **Deliverable**: `python -c "from nodeble.core.broker_tiger import TigerBroker"` works.

### Session 4: Extract the State Layer
- **What we do**: Copy `options/state.py`, adapt it for the new project. For now, keep JSON (SQLite upgrade is later). Add the atomic write + file locking.
- **Deliverable**: Can create, save, and load a SpreadState with test positions.

### Session 5: Extract the Risk Engine
- **What we do**: Copy `options/risk.py`, `engine/kill_switch.py`, `engine/circuit_breaker.py`. Wire them into a `RiskEngine` class with sequential checks.
- **Deliverable**: Risk checks pass/fail correctly against test scenarios.

### Session 6: Extract the Data Layer
- **What we do**: Copy `options/chain_screener.py`, `options/strike_selector.py`, `data/earnings.py`, `data/vix.py`. These are the market data utilities the factory needs.
- **Deliverable**: Can screen a symbol's IV rank and select spread strikes (with mock data).

### Session 7: Extract the Iron Condor Factory
- **What we do**: Copy `condor/factory.py`, `options/executor.py`, `options/manager.py`. Wire them to use the broker adapter and state layer from Sessions 3-4.
- **Deliverable**: `scan_for_condors()` runs in dry-run mode and returns candidates.

### Session 7.5: Test Migration & Dry-Run Safety
- **What we do**: Port IC-specific tests from tiger-trading (test_condor_factory.py, test_options_executor.py, test_options_manager.py, test_condor_job.py — ~1,269 lines). Run against extracted code, fix failures. Implement two-layer dry-run safety: MockBroker class + executor guard. Write explicit tests proving dry-run can't place real orders and rollback works on partial fills.
- **Note**: Scope depends on Session 1.5 findings. If extraction revealed structural changes, revisit dry-run guard design.
- **Deliverable**: All ported tests pass. Dry-run safety and rollback path proven by explicit tests.

### Session 8: Build the Entry Point (Scan + Manage Jobs)
- **What we do**: Create `run.py` — the main entry point. Supports `--mode scan`, `--mode manage`, `--mode status`, `--dry-run`. Refactor from `run_condor_job.py`.
- **Deliverable**: `python run.py --mode scan --dry-run` completes a full scan cycle against live Tiger API.

### Session 9: Add Telegram Notifications
- **What we do**: Extract the Telegram notifier. Wire it to scan/manage results. Add kill switch command via Telegram.
- **Deliverable**: Running a dry-run scan sends a notification to your Telegram.

### Session 10: Create Strategy Templates
- **What we do**: Write 3 YAML template files (conservative, moderate, aggressive IC). Add config validation on startup. Write a `config/template.yaml` with full comments (bilingual).
- **Deliverable**: 3 working templates that load and validate correctly.

### Session 11: Write the Vultr Deployment Script
- **What we do**: Write `deploy.sh` that sets up a fresh Ubuntu 24.04 VPS — installs Python, creates venv, installs deps, sets up cron, configures systemd service.
- **Deliverable**: Script runs on a fresh Vultr instance and the bot starts.

### Session 11.5: Operations Setup
- **What we do**: Build minimum operations tooling for 5 friend VPSes. (1) Health monitoring: heartbeat ping to healthchecks.io at end of each cycle, founder alerted if no ping in 2 hours. (2) Update mechanism: `update.sh` (git pull + validate config + restart), `.gitignore` for config/data/credentials. (3) Startup reconciliation: compare state file vs broker positions on boot, alert on discrepancy, never auto-fix. (4) API failure handling: retry once, then alert; escalate after 3 consecutive manage-cycle failures. (5) Log rotation via logrotate.
- **Deliverable**: Health monitoring, update script, reconciliation, API failure handling, and log rotation all working and tested on a test VPS.

### Session 12: Deploy for Your First Friend
- **What we do**: Friend spins up their own Vultr VPS. Friend runs deploy.sh themselves, enters their own Tiger API key + Telegram token. Founder provides remote guidance but never touches credentials. Run paper trading for 1 week.
- **Deliverable**: Friend receives their first Telegram notification from their own bot.

### Session 12.5: Emergency Runbook
- **What we do**: Write a bilingual (EN + CN) emergency guide for layman friends. Covers 8 scenarios: kill switch, VPS down, partial fill, unwanted position, Tiger API down, credential rotation, margin call / forced liquidation, deploy.sh failures. Plain language, actionable steps.
- **Deliverable**: `docs/emergency-runbook.md` (English) + Chinese translation.

---

## Phase 2: Build Web Dashboard (Sessions 13-28)

> [!note] Updated: Web-only (no Tauri)
> Originally planned as Tauri desktop app. Changed to FastAPI + React web dashboard accessed via browser. See [[16 - Session Plan for Audit]] for rationale.

The goal: build a web dashboard that strangers can deploy on their VPS and access via browser.

### Session 13: Understand FastAPI Basics
- What is an API, what is FastAPI, how do routes work, what is JSON
- **Deliverable**: A "hello world" FastAPI app running on localhost

### Session 14: Design the API Routes
- Map out every route the frontend needs (dashboard, strategy, risk, broker, scheduler)
- Write the route stubs (return fake data)
- **Deliverable**: All API routes return mock JSON

### Session 15: Wire Real Data to API Routes
- Connect API routes to the trading engine (broker, state, risk)
- Dashboard route returns real positions, P&L
- **Deliverable**: `GET /api/dashboard` returns live data from your Tiger account

### Session 16: Understand React Basics
- What is React, components, props, state, hooks
- Build a simple counter app
- **Deliverable**: Basic understanding of React patterns

### Session 17: Set Up the Frontend Project
- Create React + TypeScript + Vite + Tailwind project
- Set up folder structure (pages, components, hooks)
- **Deliverable**: Empty app with navigation skeleton

### Session 18: Build the Dashboard Page
- Position table, P&L summary cards, activity log
- Fetch data from FastAPI backend
- **Deliverable**: Dashboard shows real positions from your trading account

### Session 19: Build the Strategy Config Page
- Template selector (radio buttons / cards)
- Parameter editor (sliders, number inputs)
- Save to backend
- **Deliverable**: Can pick a template, adjust params, save config

### Session 20: Build the Risk Controls Page
- Kill switch button (big red)
- Risk limit display (current vs max)
- Stress test results
- **Deliverable**: Can toggle kill switch from the GUI

### Session 21: Build the Broker Setup Page
- Credential input form (Tiger ID, account, private key file picker)
- Connection test button
- **Deliverable**: Can enter credentials and test broker connection

### Session 22: Build the History Page
- Closed trades table
- Cumulative P&L chart (TradingView Lightweight Charts)
- **Deliverable**: Can see historical trades and P&L chart

### Session 23: Build the Settings Page
- Telegram configuration
- Language toggle (EN/CN)
- Scheduler time configuration
- **Deliverable**: Can configure Telegram and switch language

### Session 24: Add Bilingual Support (i18n)
- Set up react-i18next
- Translate all UI strings to Chinese
- **Deliverable**: App works fully in both English and Chinese

### Session 25: Build the Onboarding Wizard
- First-run flow: Welcome → Enter credentials → Pick template → Start paper trading
- Web-based, accessed in browser
- **Deliverable**: New user can go from zero to paper trading in 5 minutes

### Session 26: Deploy Web Dashboard
- Script to run FastAPI + React together on VPS
- Nginx reverse proxy, systemd service
- User accesses at localhost:3000 or custom domain
- **Deliverable**: Dashboard accessible in browser after deploy

### Session 27: Testing & QA
- Test full flow: deploy → configure → paper trade → live trade → close position
- Test kill switch, error states, broker disconnect
- Test on a clean Vultr VPS
- **Deliverable**: Confident the dashboard works for a stranger

### Session 28: Write Documentation
- Quickstart guide (English + Chinese)
- FAQ
- Troubleshooting guide
- **Deliverable**: Documentation ready for public users

---

## Phase 3: Launch & Grow (Sessions 29+)

### Session 29: Prepare for Commercial Launch
- Terms of Service (with lawyer input)
- Pricing page
- Landing page / product website
- **Deliverable**: Ready to accept paying users

### Session 30-33: Marketing & Community
- Create content (Bilibili tutorial, blog posts)
- Post in trading communities
- Set up referral program
- **Deliverable**: First 10 strangers sign up

### Session 34+: Iterate Based on Feedback
- Add CSP strategy template
- Add Longport broker support
- Fix bugs, improve UX based on user feedback
- **Deliverable**: Continuous improvement

---

## Session Tracking

| Session | Topic | Status | Date | Notes |
|---------|-------|--------|------|-------|
| 1 | Understand the codebase | Not started | | |
| 1.5 | Extraction spike | Not started | | Decision gate |
| 2 | Set up new project repo | Not started | | |
| 3 | Extract broker adapter | Not started | | |
| 4 | Extract state layer | Not started | | |
| 5 | Extract risk engine | Not started | | |
| 6 | Extract data layer | Not started | | |
| 7 | Extract IC factory | Not started | | |
| 7.5 | Test migration + dry-run safety | Not started | | Depends on 1.5 |
| 8 | Build entry point | Not started | | |
| 9 | Add Telegram | Not started | | |
| 10 | Create templates | Not started | | |
| 11 | Vultr deploy script + guide | Not started | | |
| 11.5 | Operations setup | Not started | | |
| 12 | First friend self-deploys | Not started | | UX validation gate |
| 12.5 | Emergency runbook | Not started | | |
| 13-28 | Web dashboard (Phase 2) | Not started | | FastAPI + React |
| 29+ | Launch (Phase 3) | Not started | | |

---

**Status**: Ready to begin Session 1
**Created**: 2026-03-19
**Related**: [[05 - Architecture Draft]] | [[07 - Technology Stack]] | [[12 - Roadmap]]
