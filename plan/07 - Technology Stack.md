# Technology Stack

---

## Guiding Principles

1. **Reuse what's already built** — the Python trading engine is production-proven, don't rewrite it
2. **Solo founder** — choose technologies with the best AI-assisted development support
3. **Layman users** — the frontend must be dead simple, no terminal required
4. **Keys stay local** — user's API credentials must never leave their machine (regulatory + trust)
5. **Bilingual** — Chinese + English from day 1

---

## Recommended Architecture: Web Dashboard + Python Engine

```
┌─────────────────────────────────────────────────┐
│           Web App (User's VPS)                   │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │    Nginx (Phase 2 only)                   │   │
│  │    Static: React + TypeScript + Tailwind  │   │
│  │    Proxy: /api/* → FastAPI :8721          │   │
│  └──────────────┬───────────────────────────┘   │
│                 │ HTTP (localhost)                │
│  ┌──────────────┴───────────────────────────┐   │
│  │         Python Backend (FastAPI)          │   │
│  │         Trading Engine (existing code)    │   │
│  │         Scheduler, Risk, State, Telegram  │   │
│  └──────────────────────────────────────────┘   │
│                                                  │
│  API keys stored locally (never transmitted)     │
└─────────────────────────────────────────────────┘
```

### Why Web-Only

> [!note] Decision updated after audit review
> Originally planned as Tauri desktop app. Changed to web-only (FastAPI + React in browser) to reduce risk and timeline.

| Factor | Web App (chosen) | Tauri | Electron |
|--------|-----------------|-------|----------|
| **Learning curve** | Low (React + FastAPI only) | High (+ Rust) | Medium (+ packaging) |
| **Keys stay local** | ✅ Runs on user's VPS, accessed via browser | ✅ Native filesystem | ✅ Same |
| **Cross-platform** | Any OS with a browser | Mac + Windows + Linux | Mac + Windows + Linux |
| **Install experience** | Run deploy.sh, open browser | Download .dmg / .exe | Download .dmg / .exe |
| **AI coding support** | Great | Good | Great |
| **Packaging/signing** | None needed | .dmg signing, notarisation | .dmg signing |
| **Auto-update** | Just `git pull` + restart | Built-in updater | Built-in updater |
| **Build time for solo founder** | 3-4 months | 5-7 months | 4-6 months |

**Web wins because**: no Rust to learn, no app packaging, no signing, works on any OS. User deploys on their VPS, accesses dashboard at `localhost:3000` or a custom domain. Keys stay on their machine.

---

## Stack Breakdown

### Frontend

| Component | Choice | Why |
|-----------|--------|-----|
| **Framework** | React 18+ with TypeScript | Best AI coding support, largest ecosystem, easiest to hire for later |
| **Styling** | Tailwind CSS | Utility-first, fast to build, consistent look |
| **Charts** | TradingView Lightweight Charts | Professional look, free, widely used in trading apps |
| **State management** | Zustand or React Query | Lightweight, no Redux overhead |
| **i18n (bilingual)** | react-i18next | Standard for React internationalisation |
| **Icons** | Lucide React | Clean, consistent icon set |
| **Build** | Vite | Fast bundler, great DX |

### Backend

| Component | Choice | Why |
|-----------|--------|-----|
| **Language** | Python 3.12+ | Already built, no rewrite needed |
| **API framework** | FastAPI | Async, fast, auto-generates OpenAPI docs, great for frontend integration |
| **Scheduler** | APScheduler | In-process scheduling, no cron dependency |
| **Database** | SQLite | Upgrade from JSON files — proper queries, multi-strategy, still local/portable |
| **Trading engine** | Existing code (extracted from tiger-trading) | Battle-tested |
| **Broker SDK** | tigeropen (Tiger), future: ib_async, longport, moomoo-api | Already proven |
| **Notifications** | Telegram API (requests) | Already built |

### Web Deployment

| Component | Choice | Why |
|-----------|--------|-----|
| **Reverse proxy** | Nginx | Serves React static files, proxies API to FastAPI |
| **Process manager** | systemd | Keeps FastAPI running, auto-restart on crash |
| **Access** | localhost:3000 (or custom domain with HTTPS) | Browser-based, no install needed |
| **Updates** | `git pull && systemctl restart nodeble` | Simple, no app store needed |

### DevOps / Infrastructure

| Component | Choice | Why |
|-----------|--------|-----|
| **Version control** | Git + GitHub (private repo) | Standard |
| **CI/CD** | GitHub Actions | Build frontend assets, run tests |
| **Package manager (Python)** | uv | Fast, modern, already used in ibkr/longport projects |
| **Package manager (JS)** | pnpm | Fast, disk-efficient |
| **Testing** | pytest (backend), Vitest (frontend) | Already using pytest |

---

## Migration Path: JSON Files → SQLite

Current tiger-trading uses JSON state files. For the product, upgrade to SQLite:

| Aspect | JSON (current) | SQLite (product) |
|--------|---------------|-----------------|
| Querying | Load entire file, filter in Python | SQL queries — fast, flexible |
| Concurrent access | File locking (fragile) | Built-in WAL mode (robust) |
| History | Overwrite (lose history) | Append trades, query historical P&L |
| Multi-strategy | Separate files per strategy | Single DB, tables per entity |
| Backup | Copy file | `.backup()` API or just copy .db file |
| Portability | ✅ Human-readable | ✅ Single file, standard format |

---

## Pre-Built Strategy Templates (Ship with Product)

Instead of personalised advice, we provide **generic templates** the user selects from:

| Template | Description | Risk Level | Suggested Capital |
|----------|-------------|-----------|-------------------|
| **Conservative IC** | Wide wings (0.08-0.10 delta), SPY/QQQ only, 30-45 DTE | Low | $20K+ |
| **Moderate IC** | Medium wings (0.12-0.15 delta), major ETFs, 21-35 DTE | Medium | $30K+ |
| **Aggressive IC** | Tighter wings (0.15-0.20 delta), individual stocks, 14-28 DTE | Higher | $50K+ |
| **CSP Conservative** | Far OTM puts (0.08-0.12 delta), SPY/QQQ | Low | $20K+ |
| **CSP Moderate** | Standard puts (0.15-0.20 delta), blue chips | Medium | $30K+ |
| **Covered Call** | Weekly/monthly OTM calls on owned shares | Low | Varies (need 100 shares) |

> [!info] Regulatory note
> Templates are generic starting points, not personalised advice. Users must review and adjust all parameters themselves. This keeps us on the "software tool" side of the regulatory line. See [[11 - Regulatory Considerations]].

---

## Development Phases

> [!info] Aligned with [[12 - Roadmap]]
> Phase 1 (Month 1-3) is friends on VPS — no new code needed beyond extraction + deploy script.
> Phase 2 (Month 4-9) is building the web dashboard for self-service users.

### Phase 1: Extract & Deploy (Month 1-3)
- Extract iron condor factory from tiger-trading into standalone Python package
- Write Vultr deployment script (`deploy-vultr.sh`)
- Write strategy template YAML files (conservative, moderate, aggressive)
- Deploy for 5 friends on Vultr VPS
- Validate, gather feedback, iterate

### Phase 2a: Build Backend API (Month 4-5)
- Add FastAPI layer exposing: config CRUD, status, positions, kill switch, scan/manage triggers
- Replace JSON state with SQLite
- Add per-user config support
- Write integration tests

### Phase 2b: Build Frontend (Month 5-7)
- React + Vite frontend scaffold, served by Nginx
- Dashboard page (positions, P&L, activity log)
- Strategy configurator (template selector + parameter editor)
- Settings page (broker credentials, Telegram setup)
- Kill switch button (big red button)
- Bilingual support (English + Chinese)

### Phase 2c: Polish & Package (Month 8-9)
- Nginx + systemd deployment script
- Updates via git pull + restart
- First-run onboarding wizard (connect Tiger API → select template → paper trade)
- Documentation site (bilingual)
- Launch commercially

---

## Open Technical Questions

1. Should the Phase 1 VPS deploy require Nginx, or is direct FastAPI access on port 8721 sufficient for friends?
2. Should the dashboard require HTTPS/TLS for the VPS deployment, or is localhost-only access acceptable for Phase 1?
3. How do we handle Tiger API rate limits with multiple strategies running?
4. Should templates be updatable (we push new templates) without a full app update?

---

**Status**: Recommendation drafted — needs founder review
**Created**: 2026-03-19
**Related**: [[05 - Architecture Draft]] | [[06 - MVP Definition]] | [[12 - Roadmap]]
