# Plan Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply all changes from the approved design spec to the NODEBLE planning documents — fix contradictions across 9 docs, add 4 new sessions, add a 10-check pre-flight checklist, and update dependency chain/estimates.

**Architecture:** Pure document editing — no code changes. Each task edits one markdown file in `plan/`. Changes follow three themes: (1) Tauri → web-only, (2) founder-deploys → credential sovereignty / friend-self-deploys, (3) personalised → configurable (regulatory compliance). The spec lives at `docs/superpowers/specs/2026-03-19-plan-improvements-design.md`.

**Tech Stack:** Markdown files, git

**VPS cost note:** Vultr pricing has changed since these docs were written. The $6/month and $12/month figures are outdated. Vultr now offers a free tier (1 vCPU, 5GB RAM, 10GB disk) and paid plans starting at ~$44/month. Use "Vultr VPS (free tier or ~$6-12/month for legacy pricing — verify current Vultr pricing before advising friends)" as the standardized language until actual tier is confirmed.

---

### Task 1: Fix Doc 00 — Home (Tauri reference in navigation)

**Files:**
- Modify: `plan/00 - Home.md`

- [ ] **Step 1: Read the file and locate the Tauri reference**

Find the navigation line that says `[[07 - Technology Stack]] — Tauri + React + Python FastAPI`

- [ ] **Step 2: Fix the Tauri reference**

Change:
```
- [[07 - Technology Stack]] — Tauri + React + Python FastAPI
```
To:
```
- [[07 - Technology Stack]] — Web (FastAPI + React)
```

- [ ] **Step 3: Commit**

```bash
git add "plan/00 - Home.md"
git commit -m "docs: fix Tauri reference in Home navigation"
```

---

### Task 2: Fix Doc 04 — Product Vision (Tauri + regulatory positioning)

**Files:**
- Modify: `plan/04 - Product Vision.md`

- [ ] **Step 1: Read the file**

Read the full file. Locate three areas to fix:
1. Tier 1 description referencing "Desktop app (Tauri)"
2. Competitive comparison table with "Personalised (we help design your strategy)"
3. Any other "personalised trading automation" phrasing

- [ ] **Step 2: Fix Tier 1 description**

Find (in Product Tiers section):
```
- Desktop app (Tauri) with strategy templates
```
Replace with:
```
- Web dashboard with strategy templates
```

- [ ] **Step 3: Fix competitive comparison table**

Find the row in "What Makes Us Different" table:
```
| **Personalised** (we help design your strategy) | Self-service only |
```
Replace with:
```
| **Config-driven** (templates + user-adjustable parameters) | Self-service only |
```

- [ ] **Step 4: Fix positioning language**

Search for all instances of "personalised" in product description context. Key instances:
- Line 16: `A **personalised trading automation platform** with:` → `A **configurable trading automation platform** with:`  (preserve the bold markers `**`)
- Any other "personalised trading automation" → "configurable trading automation"
- Do NOT change: line 77 `not personalised advice` (this is a legitimate regulatory disclaimer), document titles, or any instance where "personalised" is used to describe what we DON'T do.

- [ ] **Step 5: Commit**

```bash
git add "plan/04 - Product Vision.md"
git commit -m "docs: fix Tauri refs and regulatory positioning in Product Vision"
```

---

### Task 3: Fix Doc 05 — Architecture Draft (Tauri diagram + lifecycle)

**Files:**
- Modify: `plan/05 - Architecture Draft.md`

This is the largest single edit. Doc 05 has Tauri content in the system overview diagram, project structure, main.py description, build.sh description, and the Tauri Lifecycle section.

- [ ] **Step 1: Read the file**

Read the full file (730 lines). Identify all Tauri-related sections:
- System overview ASCII diagram (lines ~7-51) — "Tauri Desktop Shell"
- Project structure `src-tauri/` entry (lines ~167-172)
- `main.py` description "Tauri lifecycle hooks" (line ~62)
- `build.sh` description "Build Tauri app (.dmg, .msi)" (line ~175)
- "Tauri Lifecycle" section (lines ~617-643)
- "Headless Mode (Vultr VPS)" section (lines ~647-681) — keep but verify

- [ ] **Step 2: Replace the system overview diagram**

Replace the entire system overview ASCII art (everything between `## System Overview` and `---`) with a new diagram showing the web architecture. Include two deployment modes:

```
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
```

- [ ] **Step 3: Fix the project structure**

In the project structure tree, replace:
```
├── src-tauri/                        # Tauri shell (Rust)
│   ├── Cargo.toml
│   ├── tauri.conf.json              # Window config, bundler settings
│   ├── src/
│   │   └── main.rs                  # Tauri entry: spawn Python backend, open window
│   └── icons/                       # App icons
```
With:
```
├── deploy/                           # Deployment config
│   ├── nginx.conf                   # Nginx reverse proxy config (Phase 2)
│   ├── nodeble.service              # systemd unit file
│   └── deploy.sh                    # Guided deployment script
```

Also fix `main.py` description from "FastAPI app + Tauri lifecycle hooks" to "FastAPI app entry point".

Also fix `build.sh` description from "Build Tauri app (.dmg, .msi)" to "Build frontend assets".

- [ ] **Step 4: Replace the Tauri Lifecycle section**

Find the "## Tauri Lifecycle" section and everything up to the next `---`. Replace entirely with:

```markdown
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
```

- [ ] **Step 5: Fix the Headless Mode section**

The "Headless Mode (Vultr VPS)" section (lines ~647-681) should be kept but fix line ~687:
- Find: `No Tauri, no frontend — CLI + Telegram only`
- Replace with: `No web dashboard — CLI + Telegram only`

- [ ] **Step 6: Verify no remaining Tauri references**

Search the file for "Tauri", "tauri", ".dmg", ".msi", "Cargo.toml", "main.rs". There should be zero hits. If any remain, fix them.

- [ ] **Step 7: Commit**

```bash
git add "plan/05 - Architecture Draft.md"
git commit -m "docs: replace Tauri architecture with web deployment in Architecture Draft"
```

---

### Task 4: Fix Doc 06 — MVP Definition (credential sovereignty + pre-flight checklist)

**Files:**
- Modify: `plan/06 - MVP Definition.md`

This is the second largest edit. Multiple sections need rewriting plus a new pre-flight checklist section.

- [ ] **Step 1: Read the file**

Read the full file (~313 lines). Locate all sections to change per the spec (Section 1.2 and Section 3).

- [ ] **Step 2: Fix the MVP hypothesis (line 12)**

Find:
```
> *Can we get 5 paying users to run our automated iron condor system with real money, hosted on our infrastructure, and are at least 2 willing to pay for it?*
```
Replace with:
```
> *Can we get 5 users to self-deploy and run our automated iron condor system with real money on their own VPS, and are at least 2 willing to pay for it?*
```

- [ ] **Step 3: Fix the MVP description (line 14)**

Find:
```
We are NOT building a GUI, a SaaS platform, or a multi-broker product. We are running our proven Iron Condor Factory on our own servers for 5 friends who trust us with their Tiger API keys.
```
Replace with:
```
We are NOT building a GUI, a SaaS platform, or a multi-broker product. We provide a deploy-ready Iron Condor Factory that 5 friends can run on their own Vultr VPS with their own Tiger API credentials.
```

- [ ] **Step 4: Fix success criteria (lines 18-20)**

Find:
```
- 5 friends open Tiger accounts and give us API credentials
```
Replace with:
```
- 5 friends open Tiger accounts, deploy the bot on their own VPS, and run with real capital
- Friend can self-deploy using deploy.sh + guide without founder SSH-ing into their VPS
```

- [ ] **Step 5: Fix "What changed" (line 24-26)**

Find:
```
- ~~CLI self-hosted~~ → We host everything (friends are layman, computers not always on)
```
Replace with:
```
- ~~CLI self-hosted~~ → Friends self-deploy on Vultr VPS with guided script
```

- [ ] **Step 6: Fix the "MVP Scope" description (around line 32)**

Find:
```
The MVP is **Tiger Trading's Iron Condor Factory, hosted on our servers for 5 friends**.
```
Replace with:
```
The MVP is **Tiger Trading's Iron Condor Factory, packaged for friends to self-deploy on their own VPS**.
```

- [ ] **Step 7: Fix Core Feature Set table**

Find the YAML config row:
```
| **YAML config** | Per-user config file on our server | ✅ Yes (needs per-user templating) |
```
Replace with:
```
| **YAML config** | Per-user config file on friend's own VPS | ✅ Yes (needs per-user templating) |
```

Find the multi-instance row:
```
| **Multi-instance hosting** | Run 5+ bot instances on our server | ⚠️ Needs work (isolation, per-user state) |
```
Replace with:
```
| **Per-user deployment** | Each friend runs their own bot instance on their own VPS | ⚠️ Needs work (deploy script, per-user config) |
```

- [ ] **Step 8: Rewrite the entire user experience code block**

The current content (lines ~51-67) contains BOTH the user journey AND the "What happens on OUR side" block inside a single code fence. Replace the ENTIRE code fence block (from the opening triple-backtick to the closing triple-backtick) with new content. The "What happens on OUR side" block is removed entirely — it described the old founder-hosted model.

New content for the code block (inside the code fence):

    # MVP user journey — credential sovereignty model

    1. Friend opens Tiger Brokers account (we guide them through it)
    2. Friend applies for Tiger Open API access, gets tiger_id + private key
    3. Friend spins up their own Vultr VPS (free tier or paid tier)
    4. Friend runs deploy.sh on their VPS — script prompts for:
       - Tiger ID, account number, private key file path
       - Telegram bot token + chat ID
       - Strategy template choice (1=Conservative, 2=Moderate, 3=Aggressive)
       No manual YAML editing required.
    5. Founder provides guidance via screen share / Telegram but never touches credentials
    6. System starts in dry-run mode for 1 week
    7. After pre-flight checklist passes, friend switches to live trading
    8. Friend can type /status, /kill, /start in Telegram to monitor & control

- [ ] **Step 9: Fix MVP vs Full Vision table**

Find:
```
| Telegram only (Vultr VPS, founder deploys)
```
Replace with:
```
| Telegram only (Vultr VPS, friend self-deploys with founder guidance)
```

- [ ] **Step 10: Fix remaining credential sovereignty contradictions**

Also fix these lines that still reference the old model:
- Line 18: `We host and run their IC bots on our servers (Mac Mini / Ubuntu server)` → Remove or rewrite to: `Friends run their own IC bots on their own Vultr VPS`
- In the MVP vs Full Vision table, find the Distribution row: `Founder deploys manually` → `Friend self-deploys with deploy.sh`

- [ ] **Step 11: Add Pre-flight Checklist section**

Add the following new section before the "Next Steps After MVP" section (near line 294). Insert the full 10-check pre-flight checklist from the spec (Section 3). The content is:

```markdown
---

## Pre-flight Checklist

> The gate between "code works" and "friend goes live with real money."
> **All 10 checks must pass before switching any friend from dry-run to live trading.**

**Ownership**: The founder runs all checks on the first friend's VPS (with the friend present via screen share). Results are recorded in `docs/preflight-log-{friend_name}.md` with pass/fail and date. No friend goes live until all 10 pass.

For friends 2-5: after the first friend validates the process, Checks 5, 6, 9, 10 can be self-administered. Checks 1-4 and 7-8 require founder involvement via screen share.

### Check 1: Dry-run isolation verified
Run full scan cycle with `--dry-run`. Confirm via test AND log audit that zero `place_option_order` / `place_option_market_order` calls reach the Tiger SDK. Both layers must be proven: MockBroker swap AND executor dry_run guard.

### Check 2: Crash recovery tested
Test against MockBroker with artificial delays between legs (e.g., 5-second sleep per leg). Kill the process mid-execution (after leg 2 fills, before leg 3). Restart. Verify:
- State file reflects the 2 filled legs correctly
- Next manage cycle detects orphaned legs via `verify_pending_fills()`
- Rollback is attempted for the partial position
- `credit_counted` flag prevents double-counting
- Telegram alert fires about the incomplete position

### Check 3: Startup reconciliation tested
Manually add a fake position to the state file that doesn't exist at the broker. Start the bot. Verify:
- Discrepancy is detected and logged
- Telegram alert sent to founder
- No auto-close or auto-open actions taken
- Bot continues running normally after the alert

### Check 4: Tiger API failure tested
Block Tiger API access (firewall rule or DNS override). Run manage cycle with open positions. Verify:
- Retry fires once after 60 seconds
- Telegram alert sent on persistent failure
- No positions modified during outage
- Bot does not crash — exits the cycle gracefully

### Check 5: Kill switch tested end-to-end
Send `/kill` via Telegram. Verify:
- `risk.yaml` kill_switch updated to `true` immediately
- Next scan cycle aborts before any broker calls
- Next manage cycle STILL runs (monitors open positions)
- Send `/kill off` — next scan cycle proceeds normally

### Check 6: Full cycle dry-run on deployed VPS
Run 5 consecutive scan + manage cycles in dry-run on the friend's actual deployed VPS. Verify:
- Telegram notifications arrive for each cycle
- State updates correctly between cycles
- Health check pings fire to healthchecks.io
- No errors in systemd journal (`journalctl -u nodeble`)

### Check 7: Config sanity validation
Review `config/strategy.yaml` for dangerous values. Verify:
- `contracts` (max per position) is within sane bounds (1-5 for $20-50K, never >10)
- `max_open_condors` is reasonable for account size
- `cash_floor` is set appropriately (at least $10K)
- `wing_width` × `contracts` × 100 does not exceed a significant % of NLV
- `python -m nodeble --validate-config` passes with no warnings

### Check 8: Account identity verified
Run `broker.get_managed_accounts()` or equivalent. Verify:
- Tiger account number returned matches `config/broker.yaml`
- NLV is plausible for the friend's account
- Prevents misconfigured bot from trading on wrong account

### Check 9: Timezone and market hours verified
From the deployed VPS, verify:
- `date` command shows correct time (VPS may default to UTC)
- Bot correctly identifies whether US market is open or closed
- Dry-run scan outside market hours: correctly skips
- Dry-run scan during market hours: proceeds normally

### Check 10: Sufficient capital verified
Run a status check. Verify:
- `cash_available` exceeds `cash_floor` + estimated margin for one iron condor
- Bot's risk checks correctly prevent trading in underfunded account
```

- [ ] **Step 12: Verify no remaining contradictions**

Search for: "our server", "give us", "we host", "send us", "our infrastructure", "founder deploys". Fix any remaining instances to match credential sovereignty.

- [ ] **Step 13: Commit**

```bash
git add "plan/06 - MVP Definition.md"
git commit -m "docs: rewrite MVP Definition for credential sovereignty + add pre-flight checklist"
```

---

### Task 5: Fix Doc 07 — Technology Stack (Tauri content)

**Files:**
- Modify: `plan/07 - Technology Stack.md`

- [ ] **Step 1: Read the file**

Read the full file (~198 lines). Identify all Tauri-related content.

- [ ] **Step 2: Fix the architecture heading and diagram**

Find:
```
## Recommended Architecture: Tauri Desktop App + Python Engine
```
Replace with:
```
## Recommended Architecture: Web Dashboard + Python Engine
```

Replace the entire Tauri architecture diagram. It starts after the heading and contains an ASCII art box with "Tauri Desktop App (User's Machine)" — replace everything from the opening triple-backtick to the closing triple-backtick (lines ~17-47) with this web diagram:

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

- [ ] **Step 3: Fix the "Why Web-Only" section**

The existing note at line ~49-65 already explains the web-only decision. Keep this section but update the heading from "Why Web-Only (Not Tauri, Not Electron)" to "Why Web-Only" since the decision is now settled, not being debated.

- [ ] **Step 4: Fix CI/CD row**

Find:
```
| **CI/CD** | GitHub Actions | Build + sign + release desktop app |
```
Replace with:
```
| **CI/CD** | GitHub Actions | Build frontend assets, run tests |
```

- [ ] **Step 5: Fix Development Phases**

In the "Development Phases" section:
- Find the info callout (line ~153): `Phase 2 (Month 4-9) is building the Tauri app for self-service users.` → Replace with: `Phase 2 (Month 4-9) is building the web dashboard for self-service users.`
- Phase 2b (lines ~169-171): Find "Tauri + React app scaffold" and "Tauri scaffold" references. Replace with: React + Vite frontend build served by Nginx.
- Phase 2c (lines ~177-178): Find `Tauri bundler: .dmg (Mac), .msi (Windows)` → `Nginx + systemd deployment script`. Find `Auto-updater` → `Updates via git pull + restart`.

- [ ] **Step 6: Fix Open Technical Questions**

Remove questions about embedding Python in Tauri or Windows Tauri support. Replace with relevant web deployment questions (e.g., HTTPS/TLS for VPS dashboard, whether to require Nginx for Phase 1).

- [ ] **Step 7: Verify no remaining Tauri references**

Search for "Tauri", "tauri", "Electron", ".dmg", ".msi", "Cargo", "main.rs". Fix any remaining hits.

- [ ] **Step 8: Commit**

```bash
git add "plan/07 - Technology Stack.md"
git commit -m "docs: replace Tauri with web architecture in Technology Stack"
```

---

### Task 6: Fix Doc 09 — Business Model (credential sovereignty + Tauri)

**Files:**
- Modify: `plan/09 - Business Model.md`

- [ ] **Step 1: Read the file**

Read the full file (~158 lines). Locate all contradictions per spec Section 1.3.

- [ ] **Step 2: Fix delivery model table and narrative**

The delivery model table is near the top (lines ~11-12). Fix both rows:
- Phase 1 row: `Vultr VPS per friend, founder deploys` → `Vultr VPS per friend, friend self-deploys with founder guidance`
- Phase 2 row: `Tauri desktop app, user installs` → `Web dashboard (FastAPI + React), user accesses via browser`

Also fix the narrative bullets under "### Why This Model" (lines ~17-19):
- `**Phase 1**: Founder handles all technical work. Friends only interact via Telegram.` → `**Phase 1**: Friend self-deploys with founder guidance. Friends interact via Telegram.`
- `**Phase 2+**: Tauri app with GUI replaces the need for any technical knowledge` → `**Phase 2+**: Web dashboard (browser-based) replaces the need for any technical knowledge`

- [ ] **Step 3: Fix pricing table**

Find:
```
| **Phase 2+ (strangers)** | $49-99/month (TBD) | Self-service Tauri app, strategy templates, Telegram alerts |
```
Replace "Self-service Tauri app" with "Self-service web dashboard".

- [ ] **Step 4: Rewrite Phase 2 recommendation narrative**

Find the block (lines ~127-131) that says "User installs a simple desktop app (Tauri/Electron)..." and the parenthetical about hosted option with encrypted key storage. Replace entire passage with:

```
User deploys web dashboard on their VPS (FastAPI + React). Dashboard accessed via browser at localhost or custom domain. Keys stay on user's VPS. No desktop app installation required.
```

- [ ] **Step 5: Remove the contradictory callout box**

Find and remove the entire callout box (near bottom, lines ~137-142) that starts with:
```
> [!info] Why Phase 1 works
```
This is the "Friends trust us with API keys" passage that directly contradicts credential sovereignty.

- [ ] **Step 6: Update open question about holding API keys**

Find:
```
1. Can we legally hold customer broker API keys in Singapore? Any MAS (Monetary Authority of Singapore) licensing required?
```
Replace with:
```
1. ~~Can we legally hold customer broker API keys in Singapore?~~ **Resolved**: We do not hold keys. Credential sovereignty model — users deploy on their own infrastructure.
```

- [ ] **Step 7: Commit**

```bash
git add "plan/09 - Business Model.md"
git commit -m "docs: fix credential sovereignty and Tauri contradictions in Business Model"
```

---

### Task 7: Fix Doc 10 — Competitive Landscape (regulatory positioning)

**Files:**
- Modify: `plan/10 - Competitive Landscape.md`

- [ ] **Step 1: Read the file**

Read the full file (~133 lines). Locate the three items to fix per spec Section 1.8.

- [ ] **Step 2: Fix competitive comparison table**

Find:
```
| **Personalised strategy design** | ✅ | ❌ | ❌ | ❌ | ❌ |
```
Replace with:
```
| **Config-driven templates** | ✅ | ❌ | ❌ | ❌ | ❌ |
```

- [ ] **Step 3: Rewrite positioning statement**

Find the positioning statement block (lines ~109-112) that says "we design your strategy with you" and "bespoke strategy design." Rewrite to:

```
> **For Chinese-speaking options traders on Tiger Brokers** who want automated income strategies but don't want to code,
> **NODEBLE** provides **configurable trading automation** with pre-built strategy templates, professional risk controls, and bilingual support.
> **Unlike** Option Alpha (English-only, no Tiger), OPITIOS (black box, no customisation), or QuantConnect (requires programming),
> **we** offer options-native templates, bilingual support, and battle-tested code running $300K+ in production.
```

- [ ] **Step 4: Fix threat response**

Find:
```
| OPITIOS expands to configurable bots | Low | Medium | Our personalisation + consulting model is different |
```
Replace with:
```
| OPITIOS expands to configurable bots | Low | Medium | Our options-native templates + bilingual support + multi-broker capability is different |
```

- [ ] **Step 5: Commit**

```bash
git add "plan/10 - Competitive Landscape.md"
git commit -m "docs: fix regulatory positioning language in Competitive Landscape"
```

---

### Task 8: Fix Doc 12 — Roadmap (Tauri + credential sovereignty + heading)

**Files:**
- Modify: `plan/12 - Roadmap.md`

- [ ] **Step 1: Read the file**

Read the full file (~144 lines). Locate all items to fix per spec Section 1.4.

- [ ] **Step 2: Fix Phase 1 heading**

Find:
```
## Phase 1: Bespoke Consulting (Month 1-3)
```
Replace with:
```
## Phase 1: Friends Validation (Month 1-3)
```

- [ ] **Step 3: Fix per-friend delivery**

Find the per-friend delivery checklist items about founder handling deployment. Replace:
```
- [ ] We handle the technical deployment (Vultr VPS setup, Python, cron, Telegram)
- [ ] Configure Tiger API credentials on their VPS
```
With:
```
- [ ] Friend runs deploy.sh on their own VPS
- [ ] Founder provides remote guidance (screen share / Telegram) but never touches credentials
```

- [ ] **Step 4: Fix infrastructure section**

Find:
```
  - We set it up via SSH — they never touch it
```
Replace with:
```
  - Friend deploys using guided script — founder provides support but never SSH-es into their VPS
```

- [ ] **Step 5: Fix Phase 2 heading and description**

Find:
```
Build the Tauri desktop app
```
Replace with:
```
Build the web dashboard (FastAPI + React)
```

Replace Tauri packaging lines (.dmg, .msi, auto-updater) with:
```
- Nginx + systemd deployment script
- Updates via git pull + restart
```

- [ ] **Step 6: Fix Phase 2 user experience**

Find the user experience list that starts with "Download NODEBLE app (Mac or Windows)" and rewrite:

```
1. Deploy NODEBLE on their VPS using deploy.sh
2. Access dashboard via browser at localhost or custom domain
3. First-run wizard in browser: enter Tiger API credentials, pick a template
4. Dashboard starts in paper trading mode
5. User reviews paper results for 1-2 weeks
6. User switches to live trading
7. Ongoing: dashboard shows positions/P&L, Telegram sends alerts
```

- [ ] **Step 7: Commit**

```bash
git add "plan/12 - Roadmap.md"
git commit -m "docs: fix Tauri refs, credential sovereignty, and regulatory heading in Roadmap"
```

---

### Task 9: Fix Doc 15 + Add New Sessions (Session 12 fix + 4 new sessions)

**Files:**
- Modify: `plan/15 - Implementation Sessions.md`

- [ ] **Step 1: Read the file**

Read the full file (~202 lines).

- [ ] **Step 2: Fix Session 12 description**

Find Session 12 description:
```
- **What we do**: Spin up a Vultr VPS for one friend. Run the deploy script. Configure their Tiger API credentials + Telegram. Run paper trading for 1 week.
```
Replace with:
```
- **What we do**: Friend spins up their own Vultr VPS. Friend runs deploy.sh themselves, enters their own Tiger API key + Telegram token. Founder provides remote guidance but never touches credentials. Run paper trading for 1 week.
```

- [ ] **Step 3: Add Session 1.5 after Session 1**

After Session 1's content block, insert:

```markdown
### Session 1.5: Extraction Spike
- **What we do**: Create a throwaway Python script outside tiger-trading. Try importing the IC factory modules (`condor.factory`, `options.executor`, `options.manager`, `options.state`, `options.risk`). Catalog every import failure, hidden dependency, and hardcoded path. Key risks: circular dependency via `run_execution_job.is_market_open()`, 13 direct `broker.*` calls in executor, `cwd = project root` assumptions.
- **Decision gate**: If extraction requires >20 hours beyond import paths, evaluate wrapping tiger-trading as a package instead.
- **Deliverable**: Dependency list with revised effort estimates. Go/no-go recommendation for extraction vs wrapping.
```

- [ ] **Step 4: Add Session 7.5 after Session 7**

After Session 7's content block, insert:

```markdown
### Session 7.5: Test Migration & Dry-Run Safety
- **What we do**: Port IC-specific tests from tiger-trading (test_condor_factory.py, test_options_executor.py, test_options_manager.py, test_condor_job.py — ~1,269 lines). Run against extracted code, fix failures. Implement two-layer dry-run safety: MockBroker class + executor guard. Write explicit tests proving dry-run can't place real orders and rollback works on partial fills.
- **Note**: Scope depends on Session 1.5 findings. If extraction revealed structural changes, revisit dry-run guard design.
- **Deliverable**: All ported tests pass. Dry-run safety and rollback path proven by explicit tests.
```

- [ ] **Step 5: Add Session 11.5 after Session 11**

After Session 11's content block, insert:

```markdown
### Session 11.5: Operations Setup
- **What we do**: Build minimum operations tooling for 5 friend VPSes. (1) Health monitoring: heartbeat ping to healthchecks.io at end of each cycle, founder alerted if no ping in 2 hours. (2) Update mechanism: `update.sh` (git pull + validate config + restart), `.gitignore` for config/data/credentials. (3) Startup reconciliation: compare state file vs broker positions on boot, alert on discrepancy, never auto-fix. (4) API failure handling: retry once, then alert; escalate after 3 consecutive manage-cycle failures. (5) Log rotation via logrotate.
- **Deliverable**: Health monitoring, update script, reconciliation, API failure handling, and log rotation all working and tested on a test VPS.
```

- [ ] **Step 6: Add Session 12.5 after Session 12**

After Session 12's content block, insert:

```markdown
### Session 12.5: Emergency Runbook
- **What we do**: Write a bilingual (EN + CN) emergency guide for layman friends. Covers 8 scenarios: kill switch, VPS down, partial fill, unwanted position, Tiger API down, credential rotation, margin call / forced liquidation, deploy.sh failures. Plain language, actionable steps.
- **Deliverable**: `docs/emergency-runbook.md` (English) + Chinese translation.
```

- [ ] **Step 7: Update the Session Tracking table**

Add the 4 new sessions to the tracking table at the bottom of the file:

```markdown
| 1.5 | Extraction spike | Not started | | Decision gate |
| 7.5 | Test migration + dry-run safety | Not started | | Depends on 1.5 |
| 11.5 | Operations setup | Not started | | |
| 12.5 | Emergency runbook | Not started | | |
```

- [ ] **Step 8: Commit**

```bash
git add "plan/15 - Implementation Sessions.md"
git commit -m "docs: add 4 new sessions (1.5, 7.5, 11.5, 12.5) and fix Session 12 in Implementation Sessions"
```

---

### Task 10: Update Doc 16 — Session Plan for Audit (dependency chain + estimates)

**Files:**
- Modify: `plan/16 - Session Plan for Audit.md`

- [ ] **Step 1: Read the file**

Read the full file (~206 lines).

- [ ] **Step 2: Update the Phase 1 session table**

Find the Phase 1 session breakdown table (it's a markdown table with columns: #, Session, What We Do, Deliverable, Risk/Difficulty). Insert 4 new rows at the correct positions. Each new row must match the existing table's column format exactly. Insert each row as a new line between the existing rows:

After the Session 1 row (line ~44), insert:
```
| 1.5 | Extraction spike | Try importing IC factory modules outside tiger-trading, catalog hidden deps | Dependency list + go/no-go recommendation | Low-Medium |
```

After Session 7 row, add:
```
| 7.5 | Test migration + dry-run + rollback | Port 1,269 lines of IC tests, implement MockBroker + executor guard, test rollback path | All tests pass, dry-run safety proven | Medium |
```

After Session 11 row, add:
```
| 11.5 | Operations setup | Health monitoring, update.sh, startup reconciliation, API failure handling, log rotation | Ops tooling working on test VPS | Medium |
```

After Session 12 row, add:
```
| 12.5 | Emergency runbook | Write bilingual emergency guide (8 scenarios) for layman friends | docs/emergency-runbook.md | Low |
```

- [ ] **Step 3: Update the dependency chain diagram**

Replace the existing Phase 1 dependency diagram with the updated version from the spec:

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

- [ ] **Step 4: Update effort estimates**

Find the Phase 1 Risk Assessment or effort section. Update or add:

```markdown
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
```

- [ ] **Step 5: Fix Session 12 description if present**

If Doc 16 has its own Session 12 description (it may), ensure it matches the credential sovereignty model (friend self-deploys, founder provides guidance, never touches credentials).

- [ ] **Step 6: Commit**

```bash
git add "plan/16 - Session Plan for Audit.md"
git commit -m "docs: update dependency chain and effort estimates in Session Plan for Audit"
```

---

### Task 11: Final verification pass

**Files:**
- All modified files in `plan/`

- [ ] **Step 1: Search all plan docs for remaining "Tauri" references**

Run: Search for "Tauri" (case-insensitive) across all `plan/*.md` files. The only acceptable hits are in Doc 07's "Why Web-Only" section where Tauri is discussed as the rejected option, and Doc 11 (Regulatory) which is not being modified.

- [ ] **Step 2: Search for remaining "founder deploys" / "we host" language**

Run: Search for "founder deploys", "we host", "our server", "give us", "send us" across `plan/*.md`. Fix any remaining contradictions to credential sovereignty.

- [ ] **Step 3: Search for remaining "personalised" / "bespoke" in product positioning**

Run: Search for "personalised", "bespoke" across `plan/*.md`. The only acceptable hits are in Doc 11 (Regulatory Considerations) where these terms are discussed as things to avoid, and quoted "What changed" notes.

- [ ] **Step 4: Verify VPS cost consistency**

Search for "$6", "$12/month" across `plan/*.md`. The old $6/month and $12/month Vultr figures are outdated. Replace specific dollar amounts with consistent language. Use one of:
- For brief mentions: `Vultr VPS`
- For detailed mentions: `Vultr VPS (verify current pricing at vultr.com — free tier available)`
- Do NOT invent specific dollar amounts. The actual cost depends on the tier chosen.

- [ ] **Step 5: Commit any final fixes**

```bash
git add plan/
git commit -m "docs: final verification pass — fix remaining contradictions"
```

(Skip this commit if no changes were needed.)
