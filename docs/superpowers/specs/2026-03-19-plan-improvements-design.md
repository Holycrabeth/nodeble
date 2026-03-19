# Plan Improvements Design Spec

**Date**: 2026-03-19
**Scope**: Surgical fixes to the NODEBLE implementation plan — resolve document contradictions, add missing technical sessions, add pre-flight safety checklist.
**Approach**: Fix what's wrong without restructuring. Update 4 existing docs, add 4 sessions, add 1 checklist.
**Note**: Line numbers reference the documents as of 2026-03-19. Use surrounding text context to locate sections if line numbers have drifted.

---

## 1. Document Contradiction Fixes

### 1.1 Doc 05 — Architecture Draft

**Problem**: Contains 5+ pages of Tauri lifecycle details (Rust entry point, .dmg packaging, tray icon behavior) that are obsolete after the web-only decision.

**Changes**:
- Remove the "Tauri Lifecycle" section (lines 617-643)
- Remove `src-tauri/` from the project structure
- Replace with a "Web Deployment" section describing: Nginx serves React static files, reverse-proxies `/api/*` to FastAPI on port 8721, systemd manages the backend process
- Replace `src-tauri/` in project structure with `deploy/` containing: `nginx.conf`, `nodeble.service` (systemd unit), `deploy.sh`
- Keep all other sections (DB schema, data flows, broker adapter, strategy protocol, scan/manage cycles) — these are still valid regardless of delivery mechanism

### 1.2 Doc 06 — MVP Definition

**Problem**: Describes a founder-hosted model where friends send API credentials to the founder. Contradicts credential sovereignty principle established in Docs 09, 11, and 16. The contradiction appears in multiple sections: the MVP Goal, the user experience flow, and the "What happens on OUR side" block.

**Changes**:
- Rewrite the **MVP Goal** section (lines 12-14):
  - Remove: *"We are running our proven Iron Condor Factory on our own servers for 5 friends who trust us with their Tiger API keys"*
  - Replace with: *"We provide a deploy-ready Iron Condor Factory that 5 friends can run on their own Vultr VPS with their own Tiger API credentials"*
  - Remove from success criteria: *"5 friends open Tiger accounts and give us API credentials"*
  - Replace with: *"5 friends open Tiger accounts, deploy the bot on their own VPS, and run with real capital"*
- Rewrite **"What the User Experience Looks Like"** section to match credential sovereignty:
  - Friend opens Tiger account and gets API key (unchanged)
  - Friend spins up their own Vultr VPS (~$6/month)
  - Friend runs `deploy.sh` on their VPS — the script prompts interactively for Tiger ID, account number, and private key file path, then writes `config/broker.yaml` and `config/notify.yaml` locally. Friend pastes their Telegram bot token + chat ID when prompted. No manual YAML editing required.
  - Founder provides guidance via screen share / Telegram but never touches credentials
  - Friend picks a strategy template (deploy.sh shows numbered menu: 1=Conservative, 2=Moderate, 3=Aggressive) and the script copies the selected template to `config/strategy.yaml`
  - System starts in dry-run mode for 1 week
- Remove the entire **"What happens on OUR side"** block that describes creating `users/friend_name/` directories on the founder's server
- Remove: *"Friend sends us the API credentials (via secure channel)"*
- Remove: *"We create their config on our server, run dry-run to verify"*
- Remove: *"Copy their private key to users/friend_name/private_key.pem"*
- Add to success criteria: *"Friend can self-deploy using deploy.sh + guide without founder SSH-ing into their VPS"*
- Core Feature Set table (line 45): Rewrite *"Multi-instance hosting: Run 5+ bot instances on our server"* → *"Per-user deployment: Each friend runs their own bot instance on their own VPS"*
- MVP vs Full Vision table (line 283): Rewrite *"Telegram only (Vultr VPS, founder deploys)"* → *"Telegram only (Vultr VPS, friend self-deploys with founder guidance)"*
- Add new "Pre-flight Checklist" section (see Section 3 below)

### 1.3 Doc 09 — Business Model

**Problem**: Contains two contradictory models in the same document. The recommended approach says "credential sovereignty / never touch keys" but the callout box at the bottom says "friends trust us with API keys." Additionally, the Phase 2 recommendation narrative (lines 127-131) still describes Tauri/Electron.

**Changes**:
- Remove the contradictory callout box: *"Why Phase 1 Works — Friends' computers are NOT always on... Friends trust us with API keys — this is the simplest possible MVP"*
- Update the delivery model table: Phase 1 row from "founder deploys" → "Friend self-deploys with founder guidance"
- Update the delivery model table: Phase 2 row from "Tauri desktop app, user installs" → "Web dashboard (FastAPI + React), user accesses via browser"
- Update the pricing table (line 53): Change *"Self-service Tauri app"* → *"Self-service web dashboard"*
- Rewrite the Phase 2 recommendation narrative (lines 127-131): Remove *"User installs a simple desktop app (Tauri/Electron). App holds keys locally, runs the trading engine. Connects to our cloud for: dashboard, config UI, monitoring, alerts."* Replace with: *"User deploys web dashboard on their VPS (FastAPI + React). Dashboard accessed via browser at localhost or custom domain. Keys stay on user's VPS. No desktop app installation required."*

### 1.4 Doc 12 — Roadmap

**Problem**: Phase 2 description still references Tauri desktop app. Phase 1 "Per-friend delivery" section contradicts credential sovereignty.

**Changes**:
- Line 70: *"Build the Tauri desktop app"* → *"Build the web dashboard (FastAPI + React)"*
- Lines 74-76: Remove Tauri packaging (.dmg, .msi), auto-updater references. Replace with: Nginx + systemd deployment, deploy script, browser-based access
- Phase 1 per-friend delivery (lines 37-38): Remove *"We handle the technical deployment (Vultr VPS setup, Python, cron, Telegram)"* and *"Configure Tiger API credentials on their VPS"*. Replace with: *"Friend runs deploy.sh on their own VPS. Founder provides remote guidance (screen share / Telegram) but never touches credentials."*
- Phase 1 infrastructure (lines 53-55): Remove *"We set it up via SSH — they never touch it"*. Replace with: *"Friend deploys using guided script — founder provides support but never SSH-es into their VPS"*
- Phase 2 user experience (lines 77-84): Rewrite *"Download NODEBLE app (Mac or Windows)"* and the desktop-app-centric flow to describe the web dashboard deployment: *"Deploy NODEBLE on their VPS using deploy.sh. Access dashboard via browser. First-run wizard in browser: enter Tiger API credentials, pick a template, start paper trading."*

---

## 2. New Technical Sessions

Four sessions inserted into Phase 1 to fill identified gaps. Slotted by dependency, not renumbered.

### 2.1 Session 1.5: Extraction Spike

**Position**: After Session 1 (understand codebase), before Session 2 (set up repo)

**Purpose**: Validate that the IC factory can actually run in isolation before committing to the extraction plan. The plan assumes "mostly import path changes" for ~4,000 lines — this spike tests that assumption.

**What to do**:
- Create a throwaway Python script outside of tiger-trading
- Try importing `condor.factory`, `options.executor`, `options.manager`, `options.state`, `options.risk`
- Catalog every import that fails, every hardcoded path, every hidden dependency
- Key known risks to verify:
  - `run_condor_job.py` imports `is_market_open()` from `run_execution_job.py` (circular dependency risk)
  - `executor.py` makes 13 direct `broker.*` calls with no abstraction layer
  - All modules assume `cwd = project root` for path resolution
  - `condor/factory.py` imports `data.chain_recorder.record_chain_snapshot` (needed?)

**Decision gate**: If the spike reveals more than ~20 hours of extraction work (beyond import paths), evaluate an alternative: wrap tiger-trading as a dependency (import it as a package) rather than extracting files. The spike deliverable must include a go/no-go recommendation with rationale.

**Deliverable**: A list of every file/function that needs modification beyond import paths, with revised effort estimates. Go/no-go recommendation for extraction vs wrapping. May change scope of Sessions 3-7.

**Estimated time**: 2-3 hours

### 2.2 Session 7.5: Test Migration & Dry-Run Safety

**Position**: After Session 7 (extract IC factory), before Session 8 (build entry point)

**Purpose**: Establish correctness of the extraction and prove dry-run safety before building the entry point.

**What to do — Test Migration**:
- Port IC-specific tests from tiger-trading into nodeble:
  - `tests/test_condor_factory.py` (395 lines)
  - `tests/test_options_executor.py` (454 lines)
  - `tests/test_options_manager.py` (247 lines)
  - `tests/test_condor_job.py` (173 lines)
- Update imports to point to nodeble module paths
- Run tests against extracted code. Fix failures until green.
- These become the regression baseline for all future changes.
- **Note**: The exact scope of test porting depends on Session 1.5 (extraction spike) findings. If the spike revealed structural changes to the extracted modules, some tests may need more than import path updates.

**What to do — Dry-Run Safety**:
- Implement two-layer dry-run protection:
  1. `MockBroker` class that implements `BrokerAdapter` protocol but logs instead of placing orders
  2. A guard in `SpreadExecutor` that checks `dry_run` flag before any `broker.place_option_order()` or `broker.place_option_market_order()` call
- Write explicit tests:
  - `test_mock_broker_never_calls_sdk`: Prove MockBroker.place_option_order() never touches tigeropen
  - `test_executor_dry_run_guard`: Prove executor with `dry_run=True` skips all order placement even with a real broker instance
  - `test_full_scan_dry_run`: Run complete scan cycle in dry-run, verify zero orders placed via broker call log

**Deliverable**: All ported tests pass. Dry-run safety proven by explicit tests.

**Estimated time**: 4-6 hours

### 2.3 Session 11.5: Operations Setup

**Position**: After Session 11 (deploy script), before Session 12 (first friend deploys)

**Purpose**: Build minimum operations tooling for monitoring and maintaining 5 friend VPSes.

**What to do**:

**Health monitoring**:
- Add a heartbeat ping at the end of each scan/manage cycle to a free monitoring service (e.g., healthchecks.io — 20 free checks)
- Each friend's VPS gets its own check URL
- If no ping within 2 hours (scan + manage run every ~1 hour during market hours), the service emails/notifies the founder
- Implementation: single HTTP GET at end of `run.py` — ~10 lines of code

**Update mechanism**:
- Ensure `config/`, `data/`, and all credential files are in `.gitignore` so `git pull` never overwrites local config or state
- Write `update.sh` that lives on each VPS: `git pull && pip install -e . && systemctl restart nodeble`
- `update.sh` must verify that `config/broker.yaml` and `config/strategy.yaml` still exist after pull (sanity check)
- When founder pushes a fix, tells friend via Telegram: "Run `bash update.sh`"
- No automatic updates — friend controls when their instance updates

**Startup reconciliation**:
- On process start (before first scan/manage), compare local state file positions against broker positions via `broker.get_positions(sec_type="OPT")` (Phase 1 uses JSON state files; Phase 2 migrates to SQLite)
- Log any discrepancies: positions in state but not in broker (phantom), positions in broker but not in state (untracked)
- Do NOT auto-fix — send discrepancy report via Telegram and continue
- Founder + friend decide manually how to handle

**API failure handling**:
- If Tiger API returns error or timeout during manage cycle: retry once after 60 seconds
- If retry also fails: send Telegram alert with error details, skip this cycle
- Do NOT leave open positions unmonitored silently — the alert is mandatory
- If Tiger API fails during scan (no open legs yet): simply skip scan, alert, no harm done

**Log rotation**:
- Configure `logrotate` for the nodeble log directory (daily rotation, keep 7 days, compress)
- A $6/month Vultr VPS has limited disk — logs from months of scan/manage cycles will accumulate without rotation
- Add to `deploy.sh`: create `/etc/logrotate.d/nodeble` config

**Deliverable**: Health monitoring pings working, `update.sh` tested on a test VPS (with `.gitignore` verification), startup reconciliation logs discrepancies, API failure retry + alert working, log rotation configured.

**Estimated time**: 6-8 hours

### 2.4 Session 12.5: Emergency Runbook

**Position**: After Session 12 (first friend deploys), before Phase 2

**Purpose**: Give layman friends a short guide they can follow when something goes wrong. Written in plain language (bilingual EN + CN).

**What to write — `docs/emergency-runbook.md`**:

**Scenario 1: Kill switch activated**
- What happened: Trading is paused. No new positions will be opened.
- What to do: Nothing — your existing positions are still monitored. The manage cycle still runs.
- How to re-enable: Send `/kill off` in Telegram.

**Scenario 2: VPS is down / bot stopped**
- What happened: Your bot isn't running. Existing positions are still open at Tiger.
- Immediate check: Open Tiger Trade app → check if positions are still there (they are — the bot doesn't affect your broker account when it's off)
- How to restart: SSH into your VPS, run `sudo systemctl restart nodeble`
- If you can't restart: Contact founder. Your positions are safe — Tiger holds them regardless of bot status.

**Scenario 3: Partial fill / incomplete position**
- What happened: The bot opened some legs of an iron condor but not all (e.g., crash after 2 of 4 legs)
- How to check: Send `/status` in Telegram — look for positions with "partial" or "pending" status
- What to do: Open Tiger Trade app → manually close the orphaned legs (the filled ones that aren't part of a complete spread)
- Contact founder for guidance on which legs to close

**Scenario 4: Bot opened a position you don't want**
- Immediate action: Send `/kill` in Telegram to prevent further trades
- How to close: Open Tiger Trade app → find the position → close each leg manually
- Contact founder for guidance

**Scenario 5: Tiger API is down**
- What happened: The bot can't reach Tiger's servers
- What the bot does: Retries once after 60 seconds. If still failing, sends you a Telegram alert and skips this cycle.
- What you should do: Nothing. Wait. Tiger outages typically resolve within hours. Your positions are safe at the broker.

**Scenario 6: Tiger API key compromised / need to rotate credentials**
- Immediate action: Send `/kill` in Telegram to stop all trading
- Go to Tiger Open API portal → generate a new private key
- On your VPS: replace the private key file at the path specified in `config/broker.yaml`
- Restart the bot: `sudo systemctl restart nodeble`
- Send `/kill off` to re-enable trading
- Verify with `/status` that the bot can connect

**Deliverable**: A 1-2 page `docs/emergency-runbook.md` in plain English (with Chinese translation in `docs/emergency-runbook-zh.md` or bilingual inline).

**Estimated time**: 3-5 hours

### Updated Phase 1 Dependency Chain

```
Session 1 (understand codebase)
    |
Session 1.5 (extraction spike) .............. NEW — validates extraction feasibility
    |
Session 2 (set up new project repo)
    |
Session 3 (broker adapter) ---> Session 7 (IC factory) ---> Session 7.5 (test migration + dry-run) ... NEW
Session 4 (state layer) ----/        /                           |
Session 5 (risk engine) ---/        /                      Session 8 (entry point)
Session 6 (data layer) --/                                      |
                                                           Session 9 (telegram)
                                                           Session 10 (templates)
                                                                |
                                                           Session 11 (deploy script)
                                                                |
                                                           Session 11.5 (operations setup) .. NEW
                                                                |
                                                           Session 12 (first friend deploys)
                                                                |
                                                           Session 12.5 (emergency runbook) . NEW
```

### Updated Phase 1 Effort Estimate

| Sessions | Hours (original) | Hours (revised) |
|----------|-----------------|-----------------|
| 1-12 (original) | ~40-60h | ~40-60h (unchanged) |
| 1.5 Extraction spike | — | 2-3h |
| 7.5 Test migration + dry-run | — | 4-6h |
| 11.5 Operations setup | — | 6-8h |
| 12.5 Emergency runbook | — | 3-5h |
| **Total Phase 1** | **~40-60h** | **~55-82h** |

Added ~15-22 hours. This extends Phase 1 by roughly 1-2 weeks part-time but significantly reduces the risk of going live with untested extraction, unverified dry-run safety, and no operations tooling.

---

## 3. Pre-flight Checklist (Added to Doc 06)

New section in MVP Definition — the gate between "code works" and "friend goes live with real money."

**All 6 checks must pass before switching any friend from dry-run to live trading.**

**Ownership**: The founder runs all checks on the first friend's VPS (with the friend present via screen share). Results are recorded in a simple checklist file (`docs/preflight-log-{friend_name}.md`) with pass/fail and date for each check. If any check fails, the failure is diagnosed and fixed before re-running that check. No friend goes live until all 6 pass.

### Check 1: Dry-run isolation verified
Run full scan cycle with `--dry-run`. Confirm via test AND log audit that zero `place_option_order` / `place_option_market_order` calls reach the Tiger SDK. Both layers must be proven working: MockBroker swap AND executor dry_run guard.

### Check 2: Crash recovery tested
Kill the process mid-execution (after leg 2 fills, before leg 3). Restart. Verify:
- State file reflects the 2 filled legs correctly
- Next manage cycle detects the orphaned legs via `verify_pending_fills()`
- `credit_counted` flag prevents double-counting the partial credit
- Telegram alert fires about the incomplete position

### Check 3: Startup reconciliation tested
Manually add a fake position to the state file that doesn't exist at the broker. Start the bot. Verify:
- Discrepancy is detected and logged
- Telegram alert sent to founder
- No auto-close or auto-open actions taken
- Bot continues running normally after the alert

### Check 4: Tiger API failure tested
Block Tiger API access (firewall rule or DNS override). Run manage cycle with open positions in state. Verify:
- Retry fires once after 60 seconds
- Telegram alert sent on persistent failure
- No positions modified during outage
- Bot does not crash — exits the cycle gracefully

### Check 5: Kill switch tested end-to-end
Send `/kill` via Telegram. Verify:
- `risk.yaml` kill_switch updated to `true` immediately
- Next scan cycle aborts before any broker calls
- Next manage cycle STILL runs (monitors open positions, just no new trades)
- Send `/kill off` — next scan cycle proceeds normally

### Check 6: Full cycle dry-run on deployed VPS
Before going live, run 5 consecutive scan + manage cycles in dry-run on the friend's actual deployed VPS. Verify:
- Telegram notifications arrive for each cycle
- State updates correctly between cycles
- Health check pings fire to healthchecks.io
- No errors in systemd journal (`journalctl -u nodeble`)

---

## 4. What This Design Does NOT Change

- Session numbering (existing 1-12 keep their numbers; new sessions use X.5 numbering)
- Phase 2 or Phase 3 plans (those are future work)
- Strategy choice (Iron Condor remains the MVP strategy)
- Tech stack decisions (Python 3.12+, FastAPI, React, uv, pnpm)
- Business model or pricing
- Regulatory approach (pure software tool, Path A)

---

## 5. Implementation Order

1. Fix contradictions in Docs 05, 06, 09, 12 (can be done in one pass)
2. Add Session 1.5, 7.5, 11.5, 12.5 to Doc 15 (Implementation Sessions)
3. Add pre-flight checklist to Doc 06
4. Update Doc 16 (Session Plan for Audit) with revised dependency chain and effort estimates

---

## 6. Note on Phase 1 Web Dashboard

Phase 1 friends interact via Telegram only — there is no web dashboard in Phase 1. The web deployment architecture described in the Doc 05 fix (Section 1.1) applies to Phase 2. In Phase 1, the FastAPI backend runs headless with systemd; the only user interface is Telegram. This should be stated explicitly in Doc 05's new "Web Deployment" section to prevent confusion.
