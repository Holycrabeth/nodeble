# Target Market

---

## Primary Niche: Chinese-Speaking Options Traders on Tiger Brokers

### Why This Niche

1. **Tiger Brokers user base is predominantly Chinese** — mainland China, Singapore, Hong Kong, Malaysia, and overseas Chinese diaspora
2. **IBKR gateway is terrible** — unreliable, clunky setup, poor UX. Tiger's API is cleaner.
3. **IBKR space is crowded** — many companies already offer automation for IBKR (QuantConnect, Composer, etc.). Stiff competition.
4. **Tiger space is underserved** — no one is offering packaged trading automation for Tiger users
5. **Founder advantage** — Yongtao is a Chinese-speaking Tiger user with 4 live systems, deep understanding of the user

### Geographic Focus

| Region | Why |
|--------|-----|
| **Singapore** | Tiger is hugely popular here; large Chinese-speaking trader community; Yongtao is based here |
| **Malaysia** | Growing Tiger user base; Chinese-speaking population |
| **Hong Kong** | Active options traders; Tiger has HK license |
| **Mainland China** | Tiger originated from China; large retail trading community |
| **Overseas Chinese** (US, Canada, Australia, UK) | Diaspora who use Tiger for US market access |

### User Profile

- **Language**: Chinese-speaking (Mandarin primary), English secondary
- **Age**: 25-45, NOT tech-savvy (very layman)
- **Account size**: $20K-$500K USD
- **Trading knowledge**: Understands options basics, knows what spreads are
- **Current behavior**: Trading options manually, or wants to start but finds it overwhelming
- **Pain point**: Repetitive manual work, missed opportunities, emotional decisions
- **Platform**: Tiger Trade app user, may also have accounts on IBKR/Longport/Moomoo

### Where to Find Them

- Personal network (founder has friends who trade options on Tiger)
- Tiger Trade community forums
- Chinese options trading groups (WeChat, Telegram, Discord)
- r/singaporefi, r/thetagang (English-speaking subset)
- Singapore/Malaysia fintech meetups
- Chinese trading education platforms (雪球 Xueqiu, 富途牛牛 community)
- YouTube/Bilibili options trading content creators

---

## Beta User Acquisition Plan

### Phase 1: Friends & Personal Network (MVP)
- Yongtao has several friends who can be onboarded immediately
- These are trusted users who can give honest feedback
- Target: 5-10 beta users from personal network

### Phase 2: Community Outreach (Post-MVP Validation)
- (TBD) Specific communities and channels to target
- (TBD) Content strategy (Chinese language tutorials?)

---

## Market Size (Rough Estimates)

> [!note] These are estimates based on public data. Needs validation.

| Metric | Estimate | Source / Reasoning |
|--------|----------|-------------------|
| **Tiger Brokers registered users** | ~2-3 million | Public filings, UP Fintech investor reports |
| **% that trade US options** | ~5-10% | Options is a subset of active traders |
| **Options-active Tiger users (TAM)** | ~100,000-300,000 | 2-3M × 5-10% |
| **% that would consider automation** | ~1-5% | Early adopters only |
| **Potential automation users (SAM)** | ~1,000-15,000 | 100-300K × 1-5% |
| **Realistic Year 1 target (SOM)** | 20-50 paying users | Conservative — friends + first community wave |
| **Realistic Year 2 target** | 100-200 paying users | With product + marketing |

### Revenue Scenarios (at $99/month)

| Users | MRR | ARR | Assessment |
|-------|-----|-----|------------|
| 20 | $1,980 | $23,760 | Covers costs, validates concept |
| 50 | $4,950 | $59,400 | Sustainable side income |
| 200 | $19,800 | $237,600 | Full lifestyle business |
| 500 | $49,500 | $594,000 | Growth business, consider hiring |

> [!info] This is a niche lifestyle business, not a VC-scale startup
> And that's perfectly fine. A $200-500K ARR business with no employees, no investors, and no burn rate is an excellent outcome. The goal is not to be a unicorn — it's to build a profitable, sustainable business that helps traders automate their strategies.

---

## Competitive Landscape (Tiger-Specific)

Detailed analysis in [[10 - Competitive Landscape]]. Summary:

- **OPITIOS AI (美股智投)**: Only real competitor — Chinese-language AI options via Tiger. But it's a black-box signal service, not configurable automation. Different value proposition.
- **ALGOGENE**: Hong Kong platform with Tiger integration. Generic, not options-strategy-focused.
- **Nobody else**: No pre-built IC/CSP/CC bots exist for Tiger. No bilingual (EN+CN) options automation exists anywhere.
- **The gap is real and wide open.**

---

## Language Strategy

**Bilingual from day 1** (English + Chinese Mandarin)
- README, docs, setup guide — bilingual
- Telegram notifications — bilingual or user-configurable language
- Error messages — bilingual
- This is a key differentiator: no competitor offers Chinese-language trading automation

## Broker Reality Check

> [!info] Gateway analysis — why Tiger wins for MVP
> Most of Yongtao's friends use **Moomoo**, but Tiger is still the right MVP broker:
>
> | Broker | Gateway Required? | User Setup Burden |
> |--------|------------------|-------------------|
> | **Tiger** | No — direct API (SDK + private key) | Low — paste credentials, done |
> | **Longport** | No — HTTPS API + token | Low — similar to Tiger |
> | **Moomoo** | Yes — OpenD gateway (local TCP) | Medium — install, configure, keep running |
> | **IBKR** | Yes — IB Gateway/TWS (local) | High — crashes, daily restarts, flaky |
>
> **Decision: Tiger-first.** Each user runs the tool on their own machine. No gateway = simpler install, fewer support tickets, faster onboarding. Ask Moomoo friends to open a Tiger account — Tiger has free account opening and the API key setup takes 10 minutes.
>
> Moomoo/IBKR support can come later when we have a more robust product with gateway setup guides.

## Demand Signal

> [!tip] Validated demand (from founder's network)
> Multiple friends have expressed interest:
> - "I want to learn how to set up one too" — recurring feedback
> - They see the value of automation but think they need to code it themselves
> - **Our product message**: You don't need to learn to code. Configure and run.
> - This is the exact gap between "cool project" and "product worth paying for"

## Open Questions

1. ~~Should the product UI/docs be in Chinese or English or both?~~ → **Bilingual** (decided)
2. Does Tiger Brokers have any partnership or marketplace program we could join?
3. Are there regulatory considerations specific to Singapore for selling trading tools?
4. What's the price sensitivity of this market? Is $50/month too high, too low?
5. Should MVP support Moomoo alongside Tiger given the beta user pool uses Moomoo?

---

**Status**: Initial draft from founder conversation
**Created**: 2026-03-19
**Related**: [[04 - Product Vision]] | [[06 - MVP Definition]]
