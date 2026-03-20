# Roadmap

---

## The Evolution: Friends (free) → Software Tool → Platform

> [!info] Regulatory constraint
> We CANNOT sell personalised strategy advice without an FA licence (see [[11 - Regulatory Considerations]]). The commercial product MUST be a self-service software tool where users configure their own strategies. This is non-negotiable.

| Phase | What It Is | Revenue Model | Timeline |
|-------|-----------|---------------|----------|
| **Phase 1** | Help 5 friends for free (validation) | Free — not a business | Month 1-3 |
| **Phase 2** | Build self-service app with GUI + templates | Software subscription | Month 3-6 |
| **Phase 3** | Launch commercially, grow user base | $49-99/month | Month 6-9 |
| **Phase 4** | Platform (multi-broker, strategy marketplace) | SaaS + marketplace fees | Year 2+ |

---

## Phase 1: Friends Validation (Month 1-3)

**Goal**: Get 5 friends running live, earning revenue, learning what clients need.

### Pre-requisites (before any client work)
- [ ] Friends open Tiger Brokers accounts
- [ ] Friends apply for Tiger Open API access
- [ ] Friends fund accounts ($20K+ USD minimum)
- [ ] Friends decide infrastructure (Mac Mini / Vultr VPS / existing PC)

### Per-friend delivery
> [!warning] Regulatory boundary
> We are helping friends for free, NOT providing financial advice commercially.
> Friends choose their OWN watchlist and parameters. We provide the tool and tech support.
> See [[11 - Regulatory Considerations]].

- [ ] Show friend the available templates (Conservative IC, Moderate IC, Aggressive IC)
- [ ] Friend picks a template and chooses their own watchlist / parameters
- [ ] Friend runs deploy.sh on their own VPS
- [ ] Founder provides remote guidance (screen share / Telegram) but never touches credentials
- [ ] Run dry-run for 1 week (paper trading)
- [ ] Friend reviews paper results and decides to go live
- [ ] Weekly check-in for first month (tech support, NOT strategy advice)

### What we learn
- How long does onboarding actually take?
- What questions do layman users ask?
- Which template do they gravitate toward? What do they change?
- What do they look at in Telegram notifications?
- What scares them? What excites them?
- How much tech support is needed ongoing?
- **Would they pay for this?** (Ask after 2 weeks of running)

### Infrastructure
- **Vultr VPS** for each friend (~$10-20/month, they pay their own server cost)
  - Friend deploys using guided script — founder provides support but never SSH-es into their VPS
  - Always on, no hardware to buy, easy for us to maintain remotely
  - Recommended: Vultr VPS (verify current pricing at vultr.com — free tier available)
- Each friend: separate VPS, separate Tiger API credentials, separate state file, separate Telegram chat
- Fully isolated — one friend's instance can't affect another's

### Revenue target
- **Phase 1 is free** — these are friends, we're testing
- Friends pay only their own Vultr VPS and Tiger account costs
- Revenue comes in Phase 2 when we take on paying clients beyond the friend circle
- Phase 1 validates: does the system work for others? do they find it valuable? would they pay?

---

## Phase 2: Build Self-Service App (Month 4-9)

**Goal**: Build the web dashboard (FastAPI + React) so strangers can onboard themselves without founder involvement.

### What we build (see [[07 - Technology Stack]] for detail)
- **Month 4-5**: FastAPI backend API, SQLite state, strategy templates
- **Month 5-7**: React frontend (dashboard, strategy config, risk controls, bilingual)
- **Month 8-9**: Nginx + systemd deployment script, Updates via git pull + restart, onboarding wizard, docs

### What the user experience looks like
1. Deploy NODEBLE on their VPS using deploy.sh
2. Access dashboard via browser at localhost or custom domain
3. First-run wizard in browser: enter Tiger API credentials, pick a template
4. Dashboard starts in paper trading mode
5. User reviews paper results for 1-2 weeks
6. User switches to live trading
7. Ongoing: dashboard shows positions/P&L, Telegram sends alerts

### Revenue target
- Launch commercially at end of Month 9
- 20-50 paying users within 3 months of launch
- $49-99/month (validated from Phase 1 conversations)

---

## Phase 3: Grow & Expand (Month 10+)

**Goal**: Grow user base. Add strategies and brokers based on demand.

### What this looks like
- Content marketing (Bilibili/YouTube tutorials in Chinese)
- Community building (Telegram group, Tiger forums)
- Add CSP strategy template (most requested after IC)
- Add Longport broker support (gateway-free, easy to add)
- Performance reporting / track record page
- Referral program

### Revenue target
- 100-200 users
- $10-20K MRR

---

## Phase 4: Platform (Year 2+)

**Goal**: Multi-broker, multi-strategy, marketplace.

### What this looks like
- Support IBKR, Longport, Moomoo (broker plugins)
- Strategy marketplace (users share/sell strategy configs)
- More strategies: CSP, covered calls, credit spreads, PMCC, stock trend-following
- Mobile app (or PWA)
- API for power users

---

## Critical Path (What Blocks Everything)

1. **Friends opening Tiger accounts** — 1-2 weeks, **start THIS WEEK**
2. **Friends getting API access** — separate application after account approved
3. **Friends signing up for Vultr** — 5 minutes, can do in parallel
4. **Strategy design sessions** — 1-on-1 with each friend, schedule while waiting for account approval

> [!warning] The bottleneck is NOT code
> The code is 90% built. The bottleneck is **Tiger account opening** (KYC, funding, API approval). Start the process THIS WEEK — everything else can happen in parallel while they wait.

### Immediate Action Items
- [ ] Message 5 friends: "I'm building something, want to try it? Open a Tiger account"
- [ ] Send them Tiger referral link (if available)
- [ ] While they wait: prepare a Vultr deployment script
- [ ] While they wait: extract Iron Condor factory into a standalone deployable package

---

**Status**: Draft
**Created**: 2026-03-19
**Related**: [[06 - MVP Definition]] | [[09 - Business Model]]
