# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

NODEBLE is a trading automation product that lets retail traders run pre-built options strategies (starting with Iron Condors) across broker platforms via a web dashboard. The founder (Ma Yongtao) is a non-developer using AI-assisted coding. The company entity is NODEBLE Limited Partnership (Singapore).

**Current status**: Planning complete, pre-implementation (Session 0). No product code exists yet. The repo contains planning documents and 4 reference trading systems to extract from.

## Repository Structure

```
nodeble/
├── plan/                    # 16 planning documents (Obsidian vault format)
│   ├── 00 - Home.md         # Hub — company info, infrastructure, navigation
│   ├── 05 - Architecture Draft.md  # Detailed technical design, project structure, DB schema
│   ├── 06 - MVP Definition.md      # What to build first, gap analysis
│   ├── 07 - Technology Stack.md     # Stack decisions (FastAPI + React, web-only)
│   ├── 15 - Implementation Sessions.md  # 30+ session guide
│   └── 16 - Session Plan for Audit.md   # Session dependencies + risk assessment
│
└── reference/               # 4 production trading systems (source code to extract from)
    ├── tiger-trading/       # Flagship — 6 strategies, 1025 tests, ~15K lines (Python 3.13)
    ├── ibkr-sell-put/       # IBKR CSP strategy (Python 3.12+, uv)
    ├── longport-sell-put/   # Longport CSP strategy (Python 3.12+, uv)
    └── moomoo-trading/      # Moomoo CC + IC strategies (Python 3.10+)
```

## Planned Product Architecture

Web-only app (Tauri was evaluated and rejected to reduce complexity):

- **Backend**: Python 3.12+, FastAPI, APScheduler, SQLite (upgrade from JSON state files)
- **Frontend**: React 18+, TypeScript, Vite, Tailwind CSS, react-i18next (EN + CN)
- **Package managers**: `uv` (Python), `pnpm` (JS)
- **Testing**: pytest (backend), Vitest (frontend)
- **Deployment**: User's own VPS (Vultr), Nginx reverse proxy, systemd
- **API port**: localhost:8721 (not exposed to network)

Key abstractions:
- `BrokerAdapter` protocol — multi-broker support (Tiger first, then IBKR/Longport/Moomoo)
- `Strategy` protocol — scan → execute → manage → status lifecycle
- `RiskEngine` — sequential fail-closed risk check pipeline

## Key Design Decisions

1. **Web-only, not desktop app** — no Rust/Tauri, simpler for solo founder
2. **Credential sovereignty** — user API keys never leave their machine; each user runs their own instance on their own VPS
3. **Extract, don't rewrite** — ~4,000 lines from tiger-trading's IC factory move with minimal changes (mostly import paths)
4. **Config-driven** — all strategy parameters in YAML, no coding required for users
5. **Fail-closed risk** — any uncertainty means don't trade (kill switch, circuit breaker, cash floor, position limits)
6. **Sequential leg execution** — multi-leg options placed one at a time with rollback on partial fills (combo orders fail silently on some brokers)
7. **Tiger first** — gateway-free API, underserved Chinese-speaking market
8. **Bilingual from day 1** — Chinese + English UI

## Working with Reference Projects

Each reference project in `reference/` has its own CLAUDE.md (in Chinese). The shared patterns across all 4 systems:

- YAML config files (strategy, risk, broker, notifications)
- JSON state with atomic writes (tempfile + rename) and file locking
- Telegram notifications with kill switch command
- scan/manage/status CLI modes with `--dry-run`
- Broker adapter pattern (upper layers never call broker SDK directly)
- Position lifecycle: pending → open → closed_profit / closed_stop / rolled / expired

The primary extraction source is `reference/tiger-trading/` (the IC factory: `condor/factory.py`, `options/executor.py`, `options/manager.py`, plus broker, risk, state, and data modules). See `plan/05 - Architecture Draft.md` § "Code Extraction Map" for the full file-by-file mapping.

## Implementation Phases

- **Phase 1 (Month 1-3)**: Extract IC factory → standalone Python package → deploy for 5 friends on Vultr VPS (Telegram-only interface, no GUI)
- **Phase 2 (Month 4-7)**: FastAPI backend API + React web dashboard (browser-based)
- **Phase 3 (Month 8+)**: Commercial launch, add CSP strategy, add Longport broker

Sessions are tracked in `plan/15 - Implementation Sessions.md`. Dependencies are in `plan/16 - Session Plan for Audit.md`.

## Regulatory Constraint

The product MUST be a self-service software tool — not financial advice. Users choose their own watchlist and parameters from generic templates. No personalized strategy recommendations. This is a hard legal boundary (no FA licence). See `plan/11 - Regulatory Considerations.md`.
