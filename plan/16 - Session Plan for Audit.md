# Implementation Session Plan — For Audit Review

> **Context**: Solo non-developer founder (Ma Yongtao) building a trading automation product using AI-assisted coding (Claude Code). This document lays out the phased implementation plan broken into 30+ sessions for audit review. Each session is designed for ~1-3 hours of focused work.

> [!important] Core Principle — Credential Sovereignty
> **Users own their own credentials. We never touch, store, or manage anyone's API keys. We provide the tool; they deploy it themselves.**
> Each user runs their own instance on their own VPS. The founder provides documentation, scripts, and guidance — but never handles a user's Tiger API key or Telegram token.

---

## Founder Profile (Relevant to Feasibility)

- Retired, full-time available
- NOT a professional developer — uses AI (Claude Code) as primary coding tool
- Deep domain expertise in trading (4 live systems, $300K+, 20+ milestones)
- Comfortable with Python scripts, SSH, terminal basics
- No frontend/React/TypeScript experience
- Strong at system design and architecture decisions

---

## Phase 1: Extract & Deploy for 5 Friends (Sessions 1-12)

**Timeline**: Month 1-3
**Goal**: Get the Iron Condor factory running on each friend's own Vultr VPS. Friends deploy themselves using `deploy.sh` and documentation. Founder provides guidance but never touches credentials. This also validates whether the install process is simple enough for self-service.
**Revenue**: None (free for friends — validation phase)
**Infrastructure**: Each friend gets their own Vultr VPS (verify current pricing at vultr.com — free tier available). We do NOT run friends' instances on the founder's local servers — this ensures the founder never holds API keys and gives better isolation between users.

### What exists today
- Iron Condor factory: 3,996 lines of production Python code across 14 files in `tiger-trading`
- Proven in live trading: $13,959 total credit collected, $2,407 realised P&L
- Tiger broker adapter: 641 lines, 49 methods, battle-tested
- Risk engine: 12 sequential checks, kill switch, circuit breaker
- Telegram notifications: full-featured bot with commands
- All code is tightly coupled to tiger-trading's directory structure and config paths

### What needs to happen
Extract the IC factory into a standalone, deployable package that can run independently on a fresh Vultr VPS with a different user's Tiger API credentials.

### Session Breakdown

| # | Session | What We Do | Deliverable | Risk/Difficulty |
|---|---------|-----------|-------------|-----------------|
| 1 | Understand the codebase | Walk through IC factory code, trace data flow from scan to execution. No coding. | Founder can explain how a scan cycle works | Low |
| 1.5 | Extraction spike | Try importing IC factory modules outside tiger-trading, catalog hidden deps | Dependency list + go/no-go recommendation | Low-Medium |
| 2 | Set up new project repo | Create `nodeble` repo, folder structure, venv, pyproject.toml, dependencies | Empty project that runs without errors | Low |
| 3 | Extract broker adapter | Copy broker.py, create BrokerAdapter protocol, TigerBroker impl, MockBroker | Can import and instantiate TigerBroker | Low |
| 4 | Extract state layer | Copy SpreadState/SpreadPosition/SpreadLeg, atomic JSON writes, file locking | Can create, save, load positions | Low |
| 5 | Extract risk engine | Copy risk checks, kill switch, circuit breaker. Wire into RiskEngine class | Risk checks pass/fail against test scenarios | Low-Medium |
| 6 | Extract data layer | Copy chain screener, strike selector, earnings, VIX modules | Can screen IV rank and select strikes | Low |
| 7 | Extract IC factory | Copy factory.py, executor.py, manager.py. Wire to broker + state from Sessions 3-4 | `scan_for_condors()` runs in dry-run mode | Medium |
| 7.5 | Test migration + dry-run + rollback | Port 1,269 lines of IC tests, implement MockBroker + executor guard, test rollback path | All tests pass, dry-run safety proven | Medium |
| 8 | Build entry point | Create run.py with --mode scan/manage/status and --dry-run. Refactor from run_condor_job.py | Full scan cycle runs against live Tiger API in dry-run | Medium |
| 9 | Add Telegram | Extract notifier, wire to scan/manage results, add kill switch command | Dry-run sends notification to Telegram | Low |
| 10 | Create templates | Write 3 YAML templates (conservative/moderate/aggressive), add config validation | Templates load and validate | Low |
| 11 | Vultr deploy script | Write deploy.sh for Ubuntu 24.04 — Python, venv, deps, cron, systemd. Write user-facing setup guide. | Script runs on fresh Vultr and bot starts; guide is clear enough for a non-developer | Medium |
| 11.5 | Operations setup | Health monitoring, update.sh, startup reconciliation, API failure handling, log rotation | Ops tooling working on test VPS | Medium |
| 12 | First friend self-deploys | Friend spins up their own Vultr VPS, runs deploy.sh themselves, fills in their own Tiger API key + Telegram token. Founder provides remote guidance (screen share / Telegram) but never touches the credentials. Paper trade 1 week. | Friend gets first Telegram notification; deploy process validated | Medium |
| 12.5 | Emergency runbook | Write bilingual emergency guide (8 scenarios) for layman friends | docs/emergency-runbook.md | Low |

### Phase 1 Dependencies
```
Session 1 (understand)
    ↓
Session 1.5 (extraction spike) .............. NEW
    ↓
Session 2 (project setup)
    ↓
Session 3 (broker) ──→ Session 7 (factory) ──→ Session 7.5 (test + dry-run) ... NEW
Session 4 (state) ───↗        ↗                       ↗
Session 5 (risk) ───↗        ↗               Session 8 (entry point)
Session 6 (data) ──↗                                ↗
                                      Session 9 (telegram) ──────↗
                                      Session 10 (templates) ────↗
                                      Session 11 (deploy script + guide) ↗
                                              ↓
                                      Session 11.5 (operations setup) .. NEW
                                              ↓
                                      Session 12 (first friend self-deploys)
                                              ↓
                                      Session 12.5 (emergency runbook) . NEW
```

### Phase 1 Risk Assessment
- **Technical risk**: Low. We're extracting working code, not writing new logic. The hardest part is untangling import paths and config references.
- **User risk**: Medium. Friends need to open Tiger accounts and fund them ($20K+). This takes 1-2 weeks and is the real bottleneck.
- **Deploy UX risk**: Medium. Session 12 is also a usability test — if a non-developer friend can follow the guide and deploy without founder intervention, the install process is good enough for Phase 2. If they can't, we need to simplify before scaling.
- **Regulatory risk**: Low. Helping friends for free is not commercial activity.

### Updated Phase 1 Effort Estimate

| Sessions | Hours |
|----------|-------|
| 1-12 (original) | ~40-60h |
| 1.5 Extraction spike | 3-5h |
| 7.5 Test migration + dry-run + rollback | 5-7h |
| 11.5 Operations setup | 8-10h |
| 12.5 Emergency runbook | 4-6h |
| **Total Phase 1** | **~60-88h** |

Added ~20-28 hours. Extends Phase 1 by ~2-3 weeks part-time but significantly reduces risk of going live with untested extraction, unverified dry-run safety, and no operations tooling.

---

## Phase 2: Build Web Dashboard (Sessions 13-30)

**Timeline**: Month 4-7
**Goal**: Build a self-service web dashboard that strangers can deploy and configure without founder involvement.
**Revenue**: $49-99/month (pricing TBD from Phase 1 validation)

> [!note] Why Web, Not Desktop App
> Originally planned as a Tauri desktop app (.dmg). **Decision: go web-only instead.**
> - FastAPI backend + React frontend, accessed in the browser at `localhost` or a simple domain
> - No Rust/Tauri to learn — eliminates the highest-risk dependency
> - Technical risk drops from HIGH to MEDIUM
> - Timeline shortens by ~2 months (removes Sessions 25-28)
> - Users access the dashboard via browser — no app installation required
> - Works on any OS without packaging or signing

### What this phase produces
A web dashboard where a user can:
1. Enter Tiger API credentials
2. Pick a strategy template (Conservative/Moderate/Aggressive IC)
3. Adjust parameters via sliders
4. Start paper trading
5. Switch to live trading
6. Monitor positions, P&L, and risk status in a dashboard
7. Toggle kill switch
8. Receive Telegram notifications
— all without touching a terminal, config file, or command line.

### Session Breakdown

| # | Session | What We Do | Deliverable | Risk/Difficulty |
|---|---------|-----------|-------------|-----------------|
| **Backend API (FastAPI)** | | | | |
| 13 | Learn FastAPI basics | What is an API, routes, JSON, request/response cycle | "Hello world" FastAPI app | Low |
| 14 | Design API routes | Map all routes (dashboard, strategy, risk, broker, scheduler), write stubs returning mock data | All routes return mock JSON | Low |
| 15 | Wire real data to API | Connect routes to trading engine (broker, state, risk). Dashboard returns real positions | `GET /api/dashboard` returns live data | Medium |
| **Frontend (React)** | | | | |
| 16 | Learn React basics | Components, props, state, hooks. Build a counter app | Basic React understanding | Low-Medium |
| 17 | Set up frontend project | React + TypeScript + Vite + Tailwind. Folder structure, navigation skeleton | Empty app with nav | Low |
| 18 | Dashboard page | Position table, P&L cards, activity log. Fetch from backend | Dashboard shows real positions | Medium |
| 19 | Strategy config page | Template selector, parameter sliders, save to backend | Can pick template and save config | Medium |
| 20 | Risk controls page | Kill switch button, risk limit display, stress test results | Can toggle kill switch from GUI | Medium |
| 21 | Broker setup page | Credential form, file picker for private key, connection test | Can enter credentials and test | Medium |
| 22 | History page | Closed trades table, P&L chart (TradingView Lightweight Charts) | Can see trade history and chart | Medium |
| 23 | Settings page | Telegram config, language toggle, scheduler times | Can configure settings | Low-Medium |
| 24 | Bilingual (i18n) | react-i18next setup, translate all strings to Chinese | App works in EN and CN | Medium |
| **Web App Integration** | | | | |
| 25 | Onboarding wizard | First-run flow: welcome → credentials → template → paper trade. Web-based, no desktop app needed. | New user zero-to-paper in 5 min via browser | Medium |
| 26 | Deploy web dashboard | Script to run FastAPI + React together. User accesses at localhost:3000 or custom domain. Nginx/systemd setup. | Dashboard accessible in browser after deploy | Medium |
| 27 | Testing & QA | Full flow test on clean machine, error states, edge cases | Confident dashboard works for a stranger | Medium |
| 28 | Documentation | Quickstart guide (EN + CN), FAQ, troubleshooting | Docs ready for public users | Medium |

### Phase 2 Dependencies
```
Sessions 13-15 (backend API) ──→ Sessions 18-23 (frontend pages) ──→ Session 25 (onboarding wizard)
Sessions 16-17 (React basics) ─↗                                           ↓
                                  Session 24 (i18n) ─────────────→ Session 26 (web deploy)
                                                                           ↓
                                                               Session 27 (QA) → Session 28 (docs)
```

### Phase 2 Risk Assessment
- **Technical risk**: MEDIUM (down from HIGH after removing Tauri). Founder has zero frontend experience, but React + FastAPI is a well-trodden path with abundant tutorials and AI tooling support.
- **Mitigation**: Session 16 is a dedicated React learning session. Web deployment (nginx + systemd) is simpler than packaging a desktop app.
- **Time risk**: MEDIUM. ~16 sessions at 2-3 hours each = 32-48 hours. Realistic in 4 months for an AI-assisted non-developer.
- **Removed risks**: No Rust/Tauri learning curve. No .dmg packaging. No app signing. No auto-updater complexity.

---

## Phase 3: Launch & Grow (Sessions 29+)

**Timeline**: Month 8+
**Goal**: Grow user base beyond friends. Add strategies and brokers based on demand.

| # | Session | What We Do | Deliverable |
|---|---------|-----------|-------------|
| 29 | Prepare commercial launch | TOS (lawyer), pricing page, landing page | Ready for paying users |
| 30 | Content marketing | Bilibili/YouTube tutorial (Chinese), blog post | First public content |
| 31 | Community building | Telegram group, Tiger forum posts, Reddit | Community channel exists |
| 32 | Referral program | Simple referral system (manual tracking initially) | Users can refer friends |
| 33 | Add CSP template | Extract CSP strategy from tiger-trading, add as second template | Two strategies available |
| 34+ | Iterate | Bug fixes, UX improvements, add Longport broker | Continuous improvement |

### Phase 3 Risk Assessment
- **Marketing risk**: HIGH. Going from friends to strangers is the hardest jump. Content marketing in Chinese trading communities is the most promising channel but requires consistent effort.
- **Support risk**: MEDIUM. Solo founder handling 50+ users' issues. Need excellent docs and a community Telegram group where users help each other.
- **Churn risk**: MEDIUM-HIGH. Options strategies have losing months. Users may blame the tool and cancel. Need to set expectations early and show historical performance including drawdowns.

---

## Critical Path Summary

```
NOW ──→ Friends open Tiger accounts (1-2 weeks, start immediately)
  ↓
Session 1-8 ──→ Standalone IC bot works in dry-run (2-3 weeks)
  ↓
Session 9-11 ──→ Telegram + templates + deploy script + guide (1-2 weeks)
  ↓
Session 12 ──→ First friend self-deploys on their own Vultr (1 day)
               [validates deploy UX — is it simple enough?]
  ↓
[ 2-3 months of friends running, gathering feedback, validating demand ]
  ↓
Session 13-28 ──→ Web dashboard (FastAPI + React, browser-based) (3-4 months)
  ↓
Session 29+ ──→ Commercial launch
```

**Total estimated time to first friend live**: 4-6 weeks
**Total estimated time to commercial web app**: 7-9 months *(was 9-12 months with Tauri)*

---

## Questions for Audit

1. Is the Phase 1 session breakdown granular enough, or should some sessions be split further?
2. ~~Is Phase 2 (Tauri app) realistic for a non-developer, or should we plan a simpler alternative (web dashboard only)?~~ **Decided: going web-only (FastAPI + React). Tauri removed. See Phase 2 note above.**
3. Are there sessions missing? (e.g., testing, security hardening, database migration)
4. Is the critical path correct? Are there hidden dependencies?
5. Is Session 12 (friend self-deploy) a sufficient UX validation gate? Should we require 3 friends to self-deploy before moving to Phase 2?
6. Is the 7-9 month timeline to commercial launch realistic or optimistic?

---

**Status**: Ready for audit review
**Created**: 2026-03-19
**Updated**: 2026-03-20 — Replaced Tauri with web dashboard; added credential sovereignty principle; updated Session 12 to self-deploy model; updated Phase 1 infrastructure notes. Added 4 new sessions (1.5, 7.5, 11.5, 12.5); updated dependency diagram; added Phase 1 effort estimate table.
**Related**: [[15 - Implementation Sessions]] | [[05 - Architecture Draft]] | [[07 - Technology Stack]] | [[12 - Roadmap]]
