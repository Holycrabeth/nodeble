# Product Vision

## The Problem

Retail traders who want to automate their strategies face a brutal choice:
- **Code it yourself** — requires Python/API expertise, months of work, risk of bugs with real money
- **Use existing platforms** (QuantConnect, Alpaca, etc.) — locked to one broker, limited strategy types, complex APIs
- **Pay for "trading bots"** — black boxes, no customisation, questionable quality

There is no product that lets a **non-technical trader** configure and run sophisticated strategies (CSPs, iron condors, credit spreads, trend-following) across **their existing broker** with **professional risk management** — in a GUI they can understand.

---

## The Solution

A **configurable trading automation platform** with:

1. **Visual Strategy Builder** — configure strategies via GUI, not code
2. **Multi-Broker Support** — plug into Tiger, IBKR, Longport, Moomoo, and more
3. **Pre-Built Strategy Templates** — CSP, covered call, iron condor, credit spread, trend-following, mean-reversion — all proven in production
4. **Professional Risk Engine** — kill switch, position limits, stress testing, Greeks monitoring
5. **Real-Time Dashboard** — portfolio view, P&L tracking, Greeks, alerts
6. **Mobile Notifications** — Telegram/push alerts for every action
7. **Paper Trading Mode** — test everything before going live

---

## Who Is It For

### Primary: Semi-Technical Retail Traders
- Have brokerage accounts with $50K-$500K
- Understand options basics (know what a CSP or covered call is)
- Want automation but don't want to code
- Currently using spreadsheets or manual execution
- Comfortable with a GUI but might also use CLI

### Secondary: Technical Traders Who Want Speed
- Can code but don't want to build infrastructure
- Want pre-built risk management and state tracking
- Want multi-broker support without writing adapters
- Would use CLI / config files for power features

### Tertiary: RIAs / Small Funds
- Managing multiple client accounts
- Need audit trail and compliance-ready logging
- Want to deploy the same strategy across accounts

---

## What Makes Us Different

| Us | Competitors |
|-----|------------|
| **Multi-broker** (Tiger, IBKR, Longport, Moomoo, more) | Usually locked to one broker |
| **Options-native** (CSP, IC, spreads, PMCC, wheel) | Most focus on stocks only |
| **Battle-tested strategies** (real money, 20+ milestones) | Academic backtests, no live proof |
| **Risk engine included** (stress test, VaR, kill switch) | Risk is an afterthought |
| **GUI for laymen + CLI for power users** | Usually one or the other |
| **Config-driven** (YAML, no coding required) | Requires Python/Pine Script |
| **Config-driven** (templates + user-adjustable parameters) | Self-service only |

---

## Product Tiers (Future — After MVP Validation)

> [!info] Pricing is TBD until validated with real users
> Phase 1 is free (friends). Pricing will be determined after Phase 1 based on willingness-to-pay conversations. Below are placeholder tiers for planning only.

### Tier 1: Self-Service
- Web dashboard with strategy templates
- User configures all parameters themselves
- Target: $49-99/month (to be validated)

### Tier 2: Premium Support
- Everything in Tier 1
- Priority Telegram support channel
- Monthly strategy performance review (automated report, not personalised advice)
- Target: $149-199/month (to be validated)

---

## Product Name Ideas (Brainstorm)
- TradeForge
- AutoStrike
- StrategyPilot
- QuotientTrading
- OrbitalTrade
- SignalDeck
- VaultTrading

---

## Key Decisions (Resolved)

| Decision | Answer | Rationale |
|----------|--------|-----------|
| **Delivery model** | Phase 1: Vultr VPS (friend self-deploys with guide). Phase 2+: Web dashboard (FastAPI + React) | Layman users can't use CLI. Web dashboard accessed via browser on their VPS |
| **Hosting** | User's own VPS or machine. Keys never leave their infra | Avoids trust issues and regulatory complications |
| **First broker** | Tiger Brokers | Gateway-free API, underserved market, Chinese user base |
| **First strategy** | Wide Iron Condor | Defined risk both sides, non-directional, founder's choice for safety |
| **Interface** | Phase 1: Telegram only. Phase 2+: Web dashboard in browser | Layman users interact via Telegram first, then get a browser-based GUI |

---

**Status**: Initial vision draft — needs market research and customer interviews
