# Regulatory Considerations

> [!danger] This is the most important document in this vault
> Getting this wrong means criminal fines up to SGD 150,000 and/or up to 3 years imprisonment. Read carefully. Consult a lawyer before launching.

---

## The Core Question

**Does our business require a financial services license from MAS?**

It depends on which model we use:

| Model | License Needed? | Why |
|-------|----------------|-----|
| **Pure software tool** — user configures all parameters themselves | Probably NO | You're selling a tool, not advice |
| **Personalised strategy design** — we pick the watchlist, delta, DTE based on client's situation | Almost certainly YES | This is "advising on investment products" under the FAA |

---

## The Regulatory Framework

### Securities and Futures Act (SFA)
- CMS license required for "regulated activities" including dealing in capital markets products and advising on investments
- Options are "capital markets products" under the SFA

### Financial Advisers Act (FAA)
- FA license required for "advising others concerning any investment product"
- **Includes**: recommending specific securities, recommending strategies tailored to a client's circumstances
- **Key principle**: the delivery mechanism doesn't matter. If a human doing it would need a license, automating it via software also needs a license ("technology neutrality")

### MAS Guidelines on Digital Advisory Services
- Explicitly covers robo-advisory and algorithmic advice
- Clear that **personalised algorithmic recommendations = financial advice = license required**

---

## What Triggers Licensing

When we do this for a client:
- "Based on your risk profile, I recommend selling puts at 0.15 delta on SPY and QQQ"
- "Let me design a personalised iron condor strategy for you"
- "Given your $20K capital, I'd configure these parameters..."

That IS financial advice. We are:
1. Recommending **specific investment products** (options on specific underlyings)
2. Recommending **specific strategy parameters** (delta, DTE, sizing)
3. **Tailoring to the client's circumstances** (their capital, risk tolerance)

### What does NOT trigger licensing

Selling a generic software tool where:
- The user chooses their own watchlist
- The user sets their own delta, DTE, profit targets
- The user configures all parameters without our recommendation
- We provide documentation/tutorials, not personalised advice
- We market it as "trading automation software" not "personalised strategy"

This is the **QuantConnect model** — sell infrastructure, not advice.

---

## Disclaimers Do NOT Protect You

> [!warning] MAS looks at substance, not labels
> A disclaimer saying "this is not financial advice" does NOT change the regulatory characterisation. If what you're doing IS financial advice in substance, it's financial advice regardless of disclaimers.
>
> Disclaimers help with civil liability between parties. They do NOT provide regulatory protection from MAS.

---

## The Impact on Our Business Model

### Our original plan (Option C — bespoke consulting):
> "Sit with each friend, design their personalised strategy, configure parameters for them"

**This is almost certainly regulated activity under the FAA.** It's textbook financial advisory.

### The safe alternative (pure software tool):
> "Sell configurable software with pre-built strategy templates. User chooses their own stocks, sets their own parameters. We provide tutorials and documentation, not personalised advice."

**This is likely NOT regulated.** We're selling a tool, like selling a calculator.

### The tension:
Our users are "very very layman" — they may not be able to configure the tool themselves. But the moment we configure it FOR them based on their situation, we're advising.

---

## Four Paths Forward

### Path A: Pure Software Tool (No License)
- Sell the bot as configurable software
- Provide excellent tutorials, docs, video walkthroughs (bilingual)
- Offer "suggested starting configurations" (generic, not personalised) — e.g., "Conservative IC Template", "Moderate IC Template"
- User must explicitly choose and set their own parameters
- We provide tech support (how to install, how the software works), NOT strategy advice
- **Risk**: low regulatory risk
- **Downside**: harder for layman users, but solvable with great UX and templates

### Path B: Get Licensed (FA License)
- Apply for Financial Adviser's licence under FAA
- Estimated cost: SGD 50,000-200,000 in legal/compliance
- Timeline: 3-6 months
- Ongoing compliance costs (audit, reporting, insurance)
- **Risk**: expensive and slow for a Phase 1 startup
- **Upside**: can legally offer personalised strategy design — the highest-value service

### Path C: Partner with Licensed Entity
- Find a licensed FA in Singapore
- Advisory component (strategy design) provided under their licence
- We provide the technology
- Revenue sharing
- **Risk**: dependent on partner, shared revenue
- **Upside**: faster than getting own license

### Path D: "Friends and Family" Exemption (Grey Area)
- For Phase 1 (5 friends, free of charge), arguably no business of "advising" is being conducted
- Helping a friend for free is not the same as running a financial advisory business
- **Risk**: this argument weakens the moment you charge for it or expand beyond close friends
- **Upside**: buys time to figure out the right structure before scaling

---

## Recommended Approach

### Phase 1 (5 friends, free): Path D — just help friends, no commercial activity
- You're helping friends for free — no business, no license issue
- Use this time to validate the concept and learn

### Phase 1.5 (before charging anyone): Consult a lawyer
- Get a formal legal opinion from a Singapore financial regulatory lawyer
- Firms: Rajah & Tann, Allen & Gledhill, WongPartnership, or boutique fintech practices
- Cost: SGD 5,000-15,000 for a legal opinion
- **This is non-negotiable before any commercial launch**

### Phase 2 (paying customers): Path A — restructure as pure software tool
- Redesign the offering so users configure everything themselves
- Provide pre-built templates (generic, not personalised)
- Invest heavily in UX to make it layman-friendly WITHOUT us advising
- Market as "trading automation software" not "personalised strategy design"

### Phase 3 (if demand exists for personalised service): Path B or C
- If customers are willing to pay premium for bespoke strategy design
- Get licensed (or partner with licensed entity)
- Offer as premium tier under proper regulatory framework

---

## Penalties for Getting It Wrong

| Violation | Penalty |
|-----------|---------|
| Carrying on regulated activity without CMS license (SFA s82) | Fine up to **SGD 150,000** and/or **3 years imprisonment** |
| Acting as financial adviser without FA licence (FAA s6) | Fine up to **SGD 75,000** and/or **3 years imprisonment** |
| Continuing offence | Additional **SGD 7,500 per day** |
| Other consequences | Prohibition orders, public reprimands, Investor Alert List, contracts voidable |

---

## Precedents

| Company | Model | License? |
|---------|-------|----------|
| **StashAway, Syfe, Endowus** (SG robo-advisors) | Personalised algo advice | ✅ CMS + FA licensed |
| **QuantConnect** (US) | Pure software platform, user codes own strategies | ❌ No advisory license |
| **Option Alpha** (US) | Pre-built templates, user configures | Operates as education/tool platform |
| **Composer** (US) | Pre-built strategies, AI-generated | ✅ SEC-registered RIA |

The pattern: **the moment you provide the strategy (not just the tool), you need a license.**

---

## Liability & Terms of Service

> [!warning] Not yet addressed — critical before Phase 2

### What happens if the bot loses a user money due to a bug?
- Need professional indemnity insurance (PI insurance)
- Need Terms of Service that clearly state:
  - No guarantee of returns
  - Software is a tool, not financial advice
  - User is responsible for their own trading decisions
  - Liability limited to subscription fees paid
  - User accepts risk of automated trading
- TOS must be drafted by a lawyer (not DIY)

### What happens during drawdown periods?
- Options strategies WILL have losing months — this is normal
- Need to set expectations upfront (in onboarding, in docs)
- Show historical performance including drawdowns
- Avoid any language that implies guaranteed returns

### Insurance
- Professional indemnity (PI) insurance — investigate cost for Singapore
- Cyber liability insurance (if holding any user data)
- Cost: TBD — include in pre-launch budget

---

## Action Items

- [ ] **Before Phase 1**: Structure as "helping friends for free" — no commercial activity
- [ ] **Before Phase 2 (charging)**: Consult Singapore financial regulatory lawyer (SGD 5-15K)
- [ ] **Before Phase 2**: Draft Terms of Service (with lawyer)
- [ ] **Before Phase 2**: Get professional indemnity insurance quote
- [ ] Design Phase 2 product as "pure software tool" with templates, not personalised advice
- [ ] Add disclaimer to app: "This is a software tool, not financial advice"

---

> [!warning] Disclaimer
> This document is research, not legal advice. Based on publicly available information about Singapore's regulatory framework. Regulations change. A qualified Singapore lawyer must be consulted before making business decisions.

---

**Status**: Researched — REQUIRES LEGAL REVIEW before any commercial activity
**Created**: 2026-03-19
**Related**: [[09 - Business Model]] | [[12 - Roadmap]]
