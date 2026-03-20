# MVP Definition

> [!note] Purpose
> This document defines the **minimum viable product** — what we build first, what we defer, and how we'll know it worked. The goal is not to build the full vision from [[04 - Product Vision]]. The goal is to **validate the core assumption** as fast as possible with the least effort.

---

## MVP Goal

**Hypothesis to validate:**

> *Can we get 5 users to self-deploy and run our automated iron condor system with real money on their own VPS, and are at least 2 willing to pay for it?*

We are NOT building a GUI, a SaaS platform, or a multi-broker product. We provide a deploy-ready Iron Condor Factory that 5 friends can run on their own Vultr VPS with their own Tiger API credentials.

**What success looks like:**
- 5 friends open Tiger accounts, deploy the bot on their own VPS, and run with real capital
- Friend can self-deploy using deploy.sh + guide without founder SSH-ing into their VPS
- System runs 30 days without manual intervention
- Friends trust it enough to keep running with real capital
- At least 2 willing to pay for the service

**What changed from original plan:**
- ~~CLI self-hosted~~ → Friends self-deploy on Vultr VPS with guided script
- ~~CSP strategy~~ → Wide Iron Condor (safer: defined risk both sides, non-directional)
- ~~Semi-technical users~~ → Very layman friends (they only interact via Telegram)

---

## MVP Scope — What's IN

The MVP is **Tiger Trading's Iron Condor Factory, packaged for friends to self-deploy on their own VPS**.

### Core Feature Set

| Feature | Description | Already Built? |
|---------|-------------|----------------|
| **Iron Condor strategy** | Wide IC on SPY/QQQ — defined risk, non-directional | ✅ Yes (Tiger Trading condor factory) |
| **Tiger Trade broker** | Full integration via tigeropen SDK | ✅ Yes |
| **YAML config** | Per-user config file on friend's own VPS | ✅ Yes (needs per-user templating) |
| **Telegram notifications** | Trade alerts, fills, daily P&L summary | ✅ Yes |
| **Kill switch via Telegram** | Emergency stop from phone | ✅ Yes |
| **Risk controls** | Position limits, cash floor, IV rank filter, stress test | ✅ Yes |
| **Paper trading / dry-run** | Simulate without placing real orders | ✅ Yes |
| **Per-user deployment** | Each friend runs their own bot instance on their own VPS | ⚠️ Needs work (deploy script, per-user config) |
| **Per-user Telegram bot** | Each user gets their own notifications | ⚠️ Needs work (separate chat IDs, maybe separate bots) |
| **Onboarding guide** | Help friends open Tiger account + get API key | ❌ Not yet |

### What the User Experience Looks Like

```
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
```

### Strategy Parameters (Wide Iron Condor Defaults)

```yaml
strategy:
  type: iron_condor
  watchlist: [USER_CHOSEN]     # personalised — each user picks their own stocks

selection:
  put_delta_min: -0.12      # wide wings — far OTM
  put_delta_max: -0.08
  call_delta_min: 0.08
  call_delta_max: 0.12
  dte_min: 21
  dte_max: 45
  min_iv_rank: 0.30
  min_credit_pct: 0.20      # minimum 20% of width as credit
  wing_width: 5              # $5 wide spreads

management:
  profit_target_pct: 0.50    # close at 50% of max credit
  stop_loss_pct: 2.00        # close at 200% of max credit
  close_at_dte: 3            # close if DTE ≤ 3

risk:
  cash_floor: 20000
  max_open_condors: 3
  max_per_symbol: 2
  kill_switch: false

notifications:
  telegram_chat_id: "FRIEND_CHAT_ID"

broker:
  tiger_id: "FRIEND_TIGER_ID"
  account: "FRIEND_ACCOUNT"
  private_key_path: "users/friend_name/private_key.pem"
```

---

## MVP Scope — What's OUT

These are **explicitly deferred**. Do not build them for MVP, even if tempting.

| Deferred Feature | Why Deferred |
|-----------------|--------------|
| **Web GUI / desktop app** | Adds months of dev time; semi-technical users don't need it |
| **Multi-broker support** (IBKR, Longport) | Tiger is strongest; validate concept first |
| **Moomoo support** | Moomoo requires OpenD gateway — adds support burden. Tiger is zero-gateway. Ask beta users to open Tiger. |
| **CSP, PMCC, credit spreads, stock strategies** | Iron condor is the chosen MVP strategy — defined risk, non-directional |
| **Visual strategy builder** | YAML is fine for the target user |
| **User accounts / multi-tenant** | Each user runs their own instance |
| **Payment integration** | Manual billing is fine for 10 beta users |
| **Backtesting UI** | We have performance history; users can see track record |
| **Streamlit dashboard** | Telegram notifications replace this for MVP |
| **Portfolio Greeks monitoring** | Advanced; not needed for single-strategy MVP |
| **Earnings blackout system** | Nice-to-have; can document as manual awareness |
| **Auto-update mechanism** | Users can `git pull` for now |

> [!warning] Scope creep risk
> Our Tiger system has 6 strategies, 1,025 tests, and a 18-page Streamlit dashboard. **None of that is the MVP.** Resist the urge to package everything. Start with one thing that works for a stranger.

---

## Target User for MVP

**The person we're building for:**

- **Chinese-speaking** options trader (Mandarin primary) — this is our niche
- Has a Tiger Trade brokerage account (or willing to open one)
- Has $20,000+ in that account (enough for wide iron condors)
- Understands options basics — knows what a spread is, understands defined risk
- Very layman — NOT comfortable with terminals or config files
- Interacts primarily via Telegram (notifications, kill switch, status)
- Currently trading options manually and wants automation
- Based in Singapore, Malaysia, Hong Kong, or overseas Chinese diaspora

**Who we are NOT targeting for MVP:**
- Complete beginners who don't know what a put option is
- Traders who only use mobile apps
- Institutional traders / RIAs
- Windows users (MVP is Mac/Linux first — easier to support)
- IBKR-only traders (crowded market, poor gateway)

**Why Tiger, not IBKR:**
- Tiger API is cleaner and more reliable than IBKR Gateway
- IBKR automation space is already crowded (QuantConnect, Composer, etc.)
- Tiger space is underserved — no packaged automation exists
- Tiger user base is predominantly Chinese — aligns with our niche

> [!note] Beta user acquisition
> - **Phase 1: Friends network** — Yongtao has several friends ready to onboard immediately
> - Phase 2: Chinese trading communities (WeChat groups, 雪球 Xueqiu, Tiger forums)
> - Phase 3: r/thetagang, r/singaporefi, options Discord servers
> - See [[08 - Target Market]] for full market analysis

---

## Success Criteria

We know the MVP succeeded when **all four** of the following are true:

| Criterion | Target | How to Measure |
|-----------|--------|----------------|
| **Beta users running with real money** | 5-10 users | Telegram group / direct check-ins |
| **Willing to pay** | ≥ 2 users commit to $50/month | Ask directly; offer 3-month free trial first |
| **System stability** | Runs 30 days without manual intervention | No support messages, no missed scans |
| **No money-losing bugs** | Zero critical errors that cause unintended trades or losses | Bug tracker / user reports |

> [!note] On the $50/month target
> This is not about revenue — it's about **validated willingness to pay**. Two people paying anything proves the concept has value. If nobody pays, we learn something important before building more.

**Leading indicators** (check after 2 weeks):
- Are beta users actively checking their Telegram notifications?
- Are they asking questions about configuring strategy parameters?
- Are they asking for *more features* (that's a good sign)?
- Are they referring other traders?

---

## What We Need to Build

Gap analysis: what exists vs what's needed for an external user to run this.

### Gap Analysis

| Component | Current State | MVP Requirement | Effort |
|-----------|--------------|-----------------|--------|
| IC strategy logic | ✅ Production-quality in Tiger Trading (condor factory) | Extract + clean up | S |
| Tiger broker integration | ✅ Full, battle-tested | Keep as-is, clean credentials | S |
| Risk engine | ✅ Full (12 checks) | Simplify to 5 core checks for MVP | M |
| YAML config | ✅ Exists but has hardcoded paths | Templatize, add defaults, full comments | S |
| Telegram notifications | ✅ Full-featured | Keep; add daily P&L summary if missing | S |
| Paper trading mode | ⚠️ Partial (dry-run exists) | Ensure it doesn't place real orders | S |
| Kill switch via Telegram | ✅ Exists | Keep as-is | XS |
| Hardcoded paths/credentials | ❌ Scattered throughout | Audit and move to config | M |
| Setup script | ❌ Doesn't exist | Create `setup.sh` for Mac + Linux | M |
| Docker option | ❌ Doesn't exist | `Dockerfile` + `docker-compose.yml` | M |
| README / Quickstart | ❌ Internal docs only | Write from scratch for external user | L |
| Error handling | ⚠️ Internal-focused errors | User-friendly messages, retry logic | M |
| Dependency management | ⚠️ Manual (pip) | `pyproject.toml` or `uv` lock file | S |
| Configuration validation | ⚠️ Minimal | Validate config on startup, clear errors | S |

### Priority Order

**Phase 1 — Make it installable (Week 1-2)**
1. Audit and remove all hardcoded paths and credentials
2. Create config template (`config/template.yaml`) with every option documented
3. Add config validation on startup
4. Write `setup.sh` (Python version check, venv creation, pip install)
5. Test full install on a clean machine

**Phase 2 — Make it trustworthy (Week 2-3)**
6. Improve error messages (user-friendly, actionable)
7. Ensure paper trading mode is bulletproof (no accidental live orders)
8. Add startup health check (can we reach Tiger API? Is market schedule loaded?)
9. Write README with Quickstart guide

**Phase 3 — Make it deployable (Week 3-4)**
10. Create `Dockerfile` and `docker-compose.yml`
11. Add daily P&L summary Telegram message (if not already complete)
12. Write "how to run with cron" and "how to run with Docker" docs
13. Beta recruit 3-5 first testers

---

## Estimated Effort

T-shirt sizing (1 developer working part-time):

| Component | Size | Est. Hours | Notes |
|-----------|------|-----------|-------|
| Credential/path cleanup | S | 3-5h | Mostly sed/grep + test |
| Config template + validation | S | 4-6h | Template already exists, needs comments |
| Setup script (`setup.sh`) | M | 6-10h | Handle Mac + Linux, Python version, venv |
| Paper trading mode hardening | S | 3-5h | Audit all order placement paths |
| Error message improvements | M | 6-10h | Go through common failure modes |
| Startup health check | S | 2-4h | Ping Tiger API, check config required fields |
| README + Quickstart guide | L | 8-15h | Most effort is clarity + screenshots |
| Dockerfile + docker-compose | M | 6-10h | Standard Python app containerization |
| Daily P&L Telegram summary | S | 3-5h | May already exist in Tiger system |
| Beta user onboarding + support | M | 5-10h | Setup calls, answering questions |
| **TOTAL** | | **~46-80h** | ~3-6 weeks part-time |

> [!note] What we're NOT rebuilding
> The Iron Condor factory itself, the Tiger broker adapter, the risk engine core, and Telegram notifications are **already done and proven**. We are wrapping existing code, not writing new logic. This is why MVP effort is low.

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Users can't install it** | High | High | Prioritise setup.sh + Docker; do 3 install test runs on clean machines before launch |
| **Tiger API changes break it** | Medium | High | Pin tigeropen SDK version; subscribe to Tiger API changelog |
| **User misconfigures and loses money** | Medium | Critical | Paper trading default ON; config validation; prominent README warnings |
| **No one wants to pay** | Medium | High | Talk to 10 target users before building; validate demand manually |
| **Tiger account required is a barrier** | Medium | Medium | Target users who already have Tiger accounts; not trying to expand market |
| **Support burden is too high** | Medium | Medium | Write excellent docs; create a Telegram group for beta users to help each other |
| **Someone reports a bug with real money at stake** | Low | Critical | Maintain kill switch at all times; give all beta users direct contact |
| **Regulatory / legal concerns** | Low | High | Clearly state: this is a tool, not financial advice; users accept risk; no managed accounts |
| **Our Tiger Trading system path conflicts with MVP** | Low | Medium | Keep MVP as a separate repo; don't modify the production Tiger system |

> [!warning] The biggest risk
> We spend 3 months polishing code and nobody wants it. The solution: **talk to potential users FIRST**. Before writing a single line of MVP code, message 10 traders and ask: "Would you run an automated iron condor bot on your Tiger account if I gave you access?" Their response shapes everything.

---

## MVP vs Full Vision

| Dimension | MVP | Full Vision (see [[04 - Product Vision]]) |
|-----------|-----|------------------------------------------|
| Strategies | Iron Condor only | IC, CSP, CC, PMCC, spreads, trend, MR |
| Brokers | Tiger only | Tiger, IBKR, Longport, Moomoo + more |
| Interface | Telegram only (Vultr VPS, friend self-deploys with founder guidance) | GUI (web) + CLI |
| Users | 5 friends, each on own VPS | Self-service, many users |
| Distribution | Friend self-deploys with deploy.sh | App download / web signup |
| Support | Founder direct (free) | Ticketing system |
| Architecture | Refactored Tiger system | New platform (see [[05 - Architecture Draft]]) |
| Revenue | Manual billing | Stripe subscription |

The MVP proves the **core value proposition**: automated options trading works and people will pay for it. Everything in the full vision is built on top of that validated foundation.

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

---

## Next Steps After MVP

If MVP succeeds (2+ paying users, stable 30 days):
1. Interview all beta users — what would make them pay more? Refer others?
2. Decide: more strategies (IC, CC) or more brokers (IBKR for larger audience)?
3. Start [[07 - Technology Stack]] decision: do we refactor or rebuild?
4. Design [[08 - Target Market]] expansion: SE Asia options traders?
5. Consider a simple web dashboard (not full GUI) for monitoring

If MVP fails:
1. Interview dropouts — what stopped them from using it?
2. Was it installation friction? Trust? Strategy performance? Wrong target user?
3. Pivot: different strategy, different broker, different user segment

---

**Status**: Draft — pending review and first user conversation
**Created**: 2026-03-19
**Related**: [[00 - Home]] | [[01 - Existing Systems Audit]] | [[04 - Product Vision]] | [[05 - Architecture Draft]]
