# Competitive Landscape

> **TL;DR**: Tiger Brokers automation is a near-vacuum. Only 2 third-party products exist (one is a black-box signal service, the other is a generic platform). Nobody offers pre-built options strategy bots for Tiger. Nobody does bilingual English+Chinese. This is a wide open niche.

---

## Tiger Brokers Specific — Almost Nobody

| Product | What It Does | Threat Level | Notes |
|---------|-------------|--------------|-------|
| **OPITIOS AI (美股智投)** | Chinese-language AI options trading via Tiger API | Medium | Black-box ML signals, not configurable strategies. Min $5K account. Opaque pricing. Closest competitor but very different approach (AI signals vs configurable bots) |
| **ALGOGENE** | Hong Kong cloud algo platform with Tiger integration | Low | Generic platform, not options-strategy-focused. More for quant developers. HK$300 free credits for Tiger users |
| **Tiger Open SDK** | Official raw API | Not a competitor | SDK, not a product. Users must build everything themselves |
| **TigerGPT** | AI assistant in Tiger app | Not a competitor | Advisory only, does NOT execute trades |

**Key insight**: OPITIOS is the only real competitor in our space — but it's a black-box AI service ("trust our model"), not a configurable tool ("design your strategy"). Completely different value proposition.

---

## General Options Automation Platforms

### Direct Competitors (options-focused, GUI, retail)

| Product | Brokers | Strategies | Pricing | GUI | Chinese | Notes |
|---------|---------|-----------|---------|-----|---------|-------|
| **Option Alpha** | tastytrade, TradeStation, Tradier, Schwab | IC, CC (synthetic), spreads, strangles | $99-149/month | Yes (no-code bot builder) | No | Most polished. NOT Tiger. $100K limit per bot |
| **Composer** | Own brokerage | Stocks, ETFs, crypto, options (newer) | $5-40/month | Yes (visual + AI) | No | Beautiful UX but options is immature |
| **SpeedBot** | Zerodha, Angel One, tastytrade | Options, stocks, futures | $90/month (US) | Yes (no-code) | No | India + US focus |

**None of these support Tiger Brokers. None offer Chinese language.**

### Signal-to-Order Bridges

| Product | Brokers | Pricing | Notes |
|---------|---------|---------|-------|
| **TradersPost** | TradeStation, IBKR, tastytrade, E*TRADE | $49-299/month | Converts TradingView alerts to trades |
| **SignalStack** | 30+ brokers (NOT Tiger) | $27/month + per-signal | Fast execution (0.45s) |
| **PickMyTrade** | IBKR, TradeStation, Tradier | $50/month | TradingView alerts to orders |

**None support Tiger.**

### Developer Platforms (require coding)

| Product | Brokers | Pricing | Notes |
|---------|---------|---------|-------|
| **QuantConnect** | IBKR, TradeStation, tastytrade, Alpaca, Schwab + more | Free-$60/month + node costs | 300K+ users, open source engine. Requires Python/C# |
| **Alpaca** | IS a broker | Free API | Best for developers. Now has MCP server for LLM trading |
| **IBridgePy** | IBKR only | Free open source | Python framework for IBKR |

**QuantConnect is impressive but requires real programming skills. Not for layman.**

---

## Chinese-Language Platforms

| Product | Type | Brokers | Options? | Notes |
|---------|------|---------|----------|-------|
| **VNPy (vn.py)** | Open source quant framework | Chinese brokers (CTP futures) | Yes (module) | 19.1K GitHub stars. Powerful but requires coding. Qt desktop GUI |
| **QUANTAXIS** | Open source quant platform | Various | Yes | Web-based. Chinese community |
| **Abu (阿布)** | Open source ML trading | Various | Yes | 9.3K GitHub stars. Chinese docs |
| **Futu/Moomoo OpenAPI** | Official API | Moomoo only | Yes | Raw SDK, not a product |
| **LongPort OpenAPI** | Official API | Longport only | Yes | Recently launched MCP server |
| **TVCBOT** | TradingView automation | Crypto exchanges only | No | Chinese team, London based |

**Key insight**: Chinese-language options automation with a GUI does not exist. VNPy is closest but requires coding. There is NO Chinese-language Option Alpha equivalent.

---

## Consulting / Bespoke Services

| Provider | Market | Pricing | Notes |
|----------|--------|---------|-------|
| **Myalgomate** (India) | Indian brokers | $120-960 per project | Custom algo development, 2-4 week delivery |
| **EffectiveSoft** | Institutional | Custom | Full-service dev shop |
| **Upwork freelancers** | Various | $10-100/hour | Quality varies wildly. Tastytrade bot: ~$300-800 |

**No one offers bespoke options automation consulting for Tiger Brokers / Chinese-speaking traders.**

---

## Market Size

| Market | Size (2024) | Projected | Growth |
|--------|------------|-----------|--------|
| Options Trading Platforms | $7.5B | $15.2B by 2033 | 8.5% CAGR |
| AI Trading Platforms | $112.3B | $334.5B by 2030 | 20% CAGR |
| US Options Volume | 15.2B contracts (2025) | — | +22% YoY |

The overall market is large and growing fast.

---

## Our Competitive Position

### What nobody else does (our moat)

| Capability | Us | Option Alpha | OPITIOS | QuantConnect | VNPy |
|------------|-----|-------------|---------|--------------|------|
| Tiger Brokers support | ✅ | ❌ | ✅ | ❌ | ❌ |
| Chinese + English bilingual | ✅ | ❌ | Chinese only | ❌ | Chinese only |
| Pre-built IC/CSP/CC strategies | ✅ | ✅ (some) | Black box | ❌ (code yourself) | ❌ (code yourself) |
| **Config-driven templates** | ✅ | ❌ | ❌ | ❌ | ❌ |
| No coding required | ✅ | ✅ | ✅ | ❌ | ❌ |
| Battle-tested with real money | ✅ ($300K+) | N/A | Unknown | N/A | N/A |
| Multiple broker support (future) | ✅ (4 proven) | 4 US brokers | Tiger only | 10+ brokers | Chinese brokers |

### Our positioning statement

> **For Chinese-speaking options traders on Tiger Brokers** who want automated income strategies but don't want to code,
> **NODEBLE** provides **configurable trading automation** with pre-built strategy templates, professional risk controls, and bilingual support.
> **Unlike** Option Alpha (English-only, no Tiger), OPITIOS (black box, no customisation), or QuantConnect (requires programming),
> **we** offer options-native templates, bilingual support, and battle-tested code running $300K+ in production.

---

## Threats & Risks

| Threat | Likelihood | Impact | Our Response |
|--------|-----------|--------|-------------|
| Tiger Brokers builds native automation | Low-Medium | High | Move faster; our multi-broker capability is a hedge |
| OPITIOS expands to configurable bots | Low | Medium | Our options-native templates + bilingual support + multi-broker capability is different |
| Option Alpha adds Tiger support | Very Low | High | Unlikely — Tiger is niche for them |
| QuantConnect adds Tiger support | Low | Medium | They target developers, not layman |
| Tiger Brokers restricts API access | Low | Critical | Diversify to Longport early |
| Copycat Chinese competitors emerge | Medium (if we succeed) | Medium | First mover + relationships + track record |

---

**Status**: Researched and drafted
**Created**: 2026-03-19
**Sources**: Web research across 30+ platforms (see research notes)
**Related**: [[04 - Product Vision]] | [[08 - Target Market]]
