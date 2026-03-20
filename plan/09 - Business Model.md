# Business Model

---

## Delivery Model (Decided)

The delivery model evolves across phases:

| Phase | Delivery | User Experience | Keys Location |
|-------|----------|----------------|---------------|
| **Phase 1** (5 friends, free) | Vultr VPS per friend, friend self-deploys with founder guidance | Telegram only | Friend's VPS (their infra) |
| **Phase 2+** (paying users) | Web dashboard (FastAPI + React), user accesses via browser | GUI app + Telegram | User's machine (never leaves) |

### Why This Model

- **Users are very layman** — they won't use CLI, edit YAML, or run cron
- **Phase 1**: Friend self-deploys with founder guidance. Friends interact via Telegram.
- **Phase 2+**: Web dashboard (browser-based) replaces the need for any technical knowledge
- **Keys always stay on user's infrastructure** — no trust issue, no regulatory issue
- **Tiger API is gateway-free** — works on VPS and desktop without local gateway

---

## Recommendation

> [!warning] Regulatory constraint shapes everything
> Personalised strategy design = financial advisory = MAS license required.
> Founder does NOT want to deal with licensing/government.
> Therefore: **pure software tool model only.** We sell a configurable tool with templates. Users make their own decisions. See [[11 - Regulatory Considerations]].

**Start with free friends (validation), build self-service software tool (commercial product).**

1. **Month 1-2**: Help 5 friends for free (not a business — just friendship). Learn what layman users struggle with.
2. **Month 3-5**: Build the self-service product — local agent app with GUI, pre-built strategy templates, bilingual docs. Users configure everything themselves.
3. **Month 6+**: Launch commercially. Sell software subscriptions. No advisory, no licensing needed.

This way you **validate demand with zero frontend code**, learn what users actually need, then build exactly that.

---

## Revenue Model

### Pricing (Draft — needs market validation)

| Tier | Price | What You Get |
|------|-------|-------------|
> [!warning] Pricing is NOT decided
> Phase 1 is free (friends). Pricing for Phase 2+ will be determined through willingness-to-pay conversations with Phase 1 users. Below is a placeholder for planning.

| Tier | Price (Placeholder) | What You Get |
|------|--------------------|-------------|
| **Phase 1 (friends)** | Free | Full IC automation, Telegram alerts, tech support |
| **Phase 2+ (strangers)** | $49-99/month (TBD) | Self-service web dashboard, strategy templates, Telegram alerts |
| **Infrastructure** | User pays own | Vultr VPS (verify current pricing at vultr.com — free tier available) or their own always-on machine |

Pricing will be validated by asking Phase 1 friends: "Would you pay for this? How much feels fair?" after 30 days of running.

### Revenue Scenarios

See [[08 - Target Market]] for market sizing. Revenue math at $99/month placeholder:

| Scenario | Users | MRR | ARR | Assessment |
|----------|-------|-----|-----|------------|
| **Year 1 target** | 20-50 | $2-5K | $24-60K | Validates business, covers costs |
| **Year 2 target** | 100-200 | $10-20K | $120-240K | Lifestyle business |
| **Stretch** | 500 | $50K | $600K | Growth business, consider hiring |

> [!info] Pricing TBD
> $99/month is a placeholder. Will be validated with Phase 1 friends after 30 days of use.

---

## Company

| Item | Detail |
|------|--------|
| **Entity** | NODEBLE Limited Partnership |
| **UEN** | T22LP0146G |
| **Type** | LLP (Limited Liability Partnership) |
| **Jurisdiction** | Singapore |
| **Status** | Active (currently dormant — ready to activate) |

**Founder situation:**
- Retired — full-time available for this venture
- Currently studying SUSS (Accountancy, considering CS/AI pivot)
- Running 4 live trading systems as proof of capability
- Infrastructure: Mac Mini (server), Desktop PC (GPU), NAS

---

## API Key & Trust Architecture

> [!warning] Tiger API has NO OAuth or delegation
> Tiger Brokers uses **RSA private key signing** for every API call. There is no OAuth, no limited-scope tokens, no read-only keys, no delegation mechanism.
>
> **Private key = full trading authority** on the account. Period.
>
> This means any model where we hold the key requires absolute trust from the user.

### Options for handling the key problem:

| Approach | How It Works | Trust Level | Feasibility |
|----------|-------------|-------------|-------------|
| **A: We hold encrypted keys on server** | User uploads .pem file, we store encrypted, run bot server-side | High trust required | Works technically, big trust ask |
| **B: Local agent on user's machine** | User installs lightweight app that holds keys locally, connects to our cloud dashboard for config/monitoring | Keys never leave user's machine | Best security, but user needs to install something + keep machine running |
| **C: User generates a SEPARATE Tiger developer account** | User registers their own Tiger developer ID, gives us only the developer ID + account. Private key stays with them. Bot runs on their machine. | Medium trust | Still needs local install |
| **D: We help set up on their machine (white-glove)** | We remote-desktop / visit, install everything on their Mac, keys stay local | Keys never leave | Doesn't scale, but perfect for first 5-10 users |
| **E: Signal-only service** | We send trade signals (Telegram: "Sell SPY 540P Apr 17 @ $4.50"), user executes manually | Zero trust needed | No automation — defeats the purpose |

### Recommendation

**Phase 1 (first 5 friends): Self-deploy with founder guidance.**

> [!important] Credential Sovereignty
> We NEVER touch, store, or manage anyone's API keys. Friends deploy themselves. Founder provides the tool, documentation, and remote guidance only.

- Friend spins up their own Vultr VPS
- Friend runs `deploy.sh` themselves, enters their own Tiger API key + Telegram token
- Friend picks a strategy template (Conservative/Moderate/Aggressive IC) and adjusts parameters
- Founder provides remote guidance (screen share / Telegram) but never handles credentials
- Private keys stay on friend's VPS — zero trust issue
- They monitor via Telegram (notifications + kill switch)
- Minimum starting capital: ~$20K USD
- Session 12 doubles as a **UX validation gate** — if friends can't self-deploy, we simplify before Phase 2

**Phase 2 (scaling to 50+ strangers): Lightweight local agent + cloud dashboard.**
User deploys web dashboard on their VPS (FastAPI + React). Dashboard accessed via browser at localhost or custom domain. Keys stay on user's VPS. No desktop app installation required.

**Phase 3 (if Tiger adds OAuth someday): Full SaaS.**
- Only possible if Tiger introduces delegated access
- Until then, Phase 2 hybrid is the ceiling

## Open Questions

1. ~~Can we legally hold customer broker API keys in Singapore?~~ **Resolved**: We do not hold keys. Credential sovereignty model — users deploy on their own infrastructure.
2. Is NODEBLE LLP the right entity type, or do we need a Pte Ltd for SaaS?
3. What are the liability implications if a user loses money due to a bug?
4. Should we require users to sign a disclaimer / terms of service?
5. Insurance — professional indemnity insurance needed?
6. Could we lobby Tiger to add OAuth or limited-scope API keys? (Would benefit us enormously)

---

**Status**: Major pivot from CLI to SaaS/hybrid — needs founder review
**Created**: 2026-03-19
**Related**: [[00 - Home]] | [[06 - MVP Definition]] | [[08 - Target Market]]
