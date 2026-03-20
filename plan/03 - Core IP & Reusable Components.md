# Core IP & Reusable Components

What we've proven in production that can become **product IP**.

---

## Proven Intellectual Property

### 1. Multi-Strategy Voting Engine
- 20+ technical indicators across 5 categories (trend, momentum, volatility, volume, composite)
- 4-gate voting system: activity → quorum → category diversity → deadband
- Configurable thresholds (buy/sell/strong)
- Backtested: 213% return, Sharpe 1.04 on conservative strategy (2020-2025)
- **Value to customers**: Plug-and-play signal generation without coding

### 2. Options Strategy Framework
- CSP / Wheel with auto-assignment detection
- Credit spreads (signal-directed)
- Iron condors (IV-driven, non-directional)
- PMCC / diagonal spreads with progressive relaxation
- Covered calls with earnings blackout
- **Value to customers**: Pre-built options strategies they can configure, not code

### 3. Adaptive Risk Management
- Multi-layered risk pipeline (kill switch → cash floor → contracts → delta → notional → stress test)
- VIX-based parameter scaling (auto-adjust in different regimes)
- Regime filtering (risk-on / cautious / defensive)
- Portfolio-level Greeks aggregation + VaR
- 7-scenario stress testing
- **Value to customers**: Professional-grade risk controls without a quant team

### 4. Universal Broker Adapter Pattern
- Proven across 4 different brokers (Tiger, IBKR, Longport, Moomoo)
- Hybrid data+execution model (use best data source + cheapest execution)
- Sequential multi-leg execution with rollback
- **Value to customers**: Use any broker they already have an account with

### 5. Atomic State & Position Lifecycle
- Crash-safe JSON persistence (tempfile + atomic rename)
- Position lifecycle: pending → open → closing → closed/rolled/expired
- File locking for concurrent access
- State backups with hourly snapshots
- **Value to customers**: Never lose track of positions, even on crashes

### 6. Config-Driven Architecture
- 100% code-free strategy configuration (YAML)
- Hot-reloadable parameters
- Strategy-scoped config directories
- **Value to customers**: Tune strategies without touching code

---

## Extractable Modules

| Module | Source | Lines | Purpose |
|--------|--------|-------|---------|
| `broker_adapter` | All 4 projects | ~2,000 | Unified broker interface |
| `signal_engine` | Tiger trading | ~1,500 | Indicator voting pipeline |
| `options_scanner` | Tiger + Moomoo | ~2,000 | Options opportunity scanner |
| `risk_engine` | Tiger (most complete) | ~800 | Risk check pipeline |
| `state_manager` | All 4 (same pattern) | ~500 | Position state persistence |
| `scheduler` | Tiger (launchd) | ~300 | Job scheduling framework |
| `notifier` | All 4 | ~200 | Telegram notification layer |
| `data_provider` | Tiger + yfinance | ~600 | Market data with caching + fallback |
| `backtester` | Tiger | ~1,000 | Walk-forward backtesting |
| `dashboard` | Tiger (Streamlit) | ~2,000 | 18-page monitoring dashboard |

**Total extractable**: ~9,000+ lines of battle-tested code

---

## What We've Learned (Operational Wisdom)

These lessons from running real money are **harder to replicate than code**:

1. **Sequential leg execution > combo orders** — combo orders fail silently on some brokers; sequential with rollback is safer
2. **Atomic state writes are non-negotiable** — we've had crashes mid-write; temp file + rename saved us
3. **Kill switch must be remote** — Telegram-accessible, not just config file
4. **Dry-run mode for everything** — customers will want to paper trade first
5. **Dedup guards prevent expensive mistakes** — cron retries can double-order
6. **Earnings blackout must be automatic** — manual tracking fails at scale
7. **VIX scaling matters** — same strategy params don't work in calm vs volatile markets
8. **Tiger API is the best data source** — even when executing elsewhere
9. **File-based state > database for single-user** — simpler, portable, debuggable
10. **Position reconciliation between state and broker** — drift happens; need cross-check
