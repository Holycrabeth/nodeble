# Existing Systems Audit

We have **4 production-proven trading automation systems** running live with real capital. This is the foundation IP for the startup.

---

## 1. Tiger Trading (Flagship)

| Attribute | Detail |
|-----------|--------|
| **Path** | `~/.tiger-trading/project/` |
| **Broker** | Tiger Brokers (tigeropen SDK) |
| **Account** | ~$319K NLV |
| **Language** | Python 3.13 |
| **Strategies** | 6 (see below) |
| **Indicators** | 20-21 per stock strategy |
| **Tests** | 1,025+ unit tests across 69 files |
| **Scheduling** | macOS launchd (15 scheduled jobs) |
| **Monitoring** | Telegram bot + Streamlit dashboard (18+ pages) |
| **Milestones** | M0-M20 tracked in git |

### Strategies
1. **Conservative** — Trend-following on 20 mega-caps (SMA/EMA/RSI/MACD voting, 213% backtest return, Sharpe 1.04)
2. **Aggressive** — Mean-reversion on 20 defensive stocks (RSI extreme, Bollinger, sentiment)
3. **Theta Harvest** — Cash-secured puts + wheel on 9 underlyings (delta -0.20 to -0.10, 50% profit target)
4. **Options Credit Spreads** — Signal-directed bull puts / bear calls (7 mega-caps)
5. **Iron Condor Factory** — IV-driven non-directional on 5 ETFs
6. **PMCC** — Poor Man's Covered Call / diagonal spreads on 8 stocks

### Key Architecture
- **Signal Pipeline**: Fetch OHLCV → Run 20 indicators → Voting system (4 gates: activity, quorum, category diversity, deadband) → Decision threshold → Earnings blackout → Position allocation
- **Execution Pipeline**: Load signal → Risk checks (kill switch, circuit breaker, max orders) → Place market orders → Fill verification → State update → Telegram notification
- **State**: Atomic JSON writes with file locking, hourly backups
- **Data**: Parquet-cached OHLCV, Tiger API primary + yfinance fallback, chain snapshots
- **Risk**: Kill switch, circuit breaker, leverage cap (1.7x), earnings blackout, price guards, stop losses, stress testing (7 scenarios)

### Unique Features
- Config-gated indicator evolution (A/B testing built-in)
- VIX scaling tiers (parameter adjustment by market regime)
- Regime filtering framework (risk-on / cautious / defensive)
- Portfolio Greeks aggregation + VaR logging
- Sequential leg execution for multi-leg options
- Comprehensive audit trail

---

## 2. IBKR Sell-Put

| Attribute | Detail |
|-----------|--------|
| **Path** | `~/.ibkr-sell-put/` (also in Dropbox) |
| **Broker** | Interactive Brokers (ib_async) |
| **Data Source** | Tiger Brokers API (hybrid model) |
| **Account** | ~$500K+ |
| **Language** | Python 3.12+ |
| **Strategy** | Cash-Secured Puts only (SPY, QQQ) |
| **Package Manager** | uv |

### Strategy Parameters
- Delta: -0.25 to -0.15
- DTE: 25-50 (ideal 35)
- IV rank minimum: 10%
- Profit target: 50% of entry premium
- Roll at DTE ≤ 7

### Key Architecture
- **Hybrid Broker**: Tiger for data (cheap, fast) + IBKR for execution (low commissions)
- **Risk**: Kill switch, cash floor ($20K), max 10 contracts, max 5 per symbol, portfolio delta cap (500), notional exposure cap (3x NLV), stress test (20% crash sim)
- **Modes**: `scan`, `manage`, `status`, `bot`
- **Dedup**: Only scans once per calendar day
- **Roll Follow-up**: Auto-scans for replacement after close

### Unique Features
- Cross-broker position reconciliation (checks IBKR positions as fallback)
- Pre-trade stress test simulation (20% market crash)
- Telegram bot with long-polling (kill switch toggle, live quotes)

---

## 3. Longport Sell-Put

| Attribute | Detail |
|-----------|--------|
| **Path** | `~/.longport-sell-put/project/` |
| **Broker** | Longport (HTTPS API, no gateway needed) |
| **Data Source** | Tiger Brokers API |
| **Account** | ~$109.5K (~852K HKD) |
| **Language** | Python 3.12+ |
| **Strategy** | Cash-Secured Puts only (SPY, QQQ) |

### Strategy Parameters
- Delta: -0.15 to -0.08 (further OTM than IBKR)
- DTE: 30-50 (ideal 40)
- IV rank minimum: 12%
- Profit target: 40% (close sooner, more cycles/year)
- Roll at DTE ≤ 14

### Key Architecture
- Same hybrid broker pattern as IBKR version
- More conservative: max 6 contracts, 3 per symbol, notional cap 3x, stress loss cap 30%
- HKD-to-USD dynamic conversion (yfinance rate + fallback)
- Target: ~17 cycles/year, ~12-15% annual return

### Unique Features
- Longport HTTPS API (no local gateway required — simpler deployment)
- Tighter risk controls (tuned for smaller account)
- Interactive Telegram bot with `/sync` command (Dropbox sync)

---

## 4. Moomoo Trading

| Attribute | Detail |
|-----------|--------|
| **Path** | `~/Dropbox/projects/moomoo-trading/` |
| **Broker** | Moomoo/Futu (OpenD gateway at 127.0.0.1:11111) |
| **Data Sources** | Tiger API (Greeks), yfinance (prices), Moomoo (quotes) |
| **Language** | Python 3.10+ |
| **Strategies** | 2: Covered Call (TSLA) + Iron Condor (TSLA, SPY) |
| **Total Code** | ~2,437 lines |

### Covered Call Strategy
- Underlying: TSLA only (100 shares, cost basis $398.07)
- Delta: 15-25 (0.20 ideal), DTE: 5-8 (weekly)
- Profit target: 50%
- Earnings blackout: 2 days

### Iron Condor Strategy
- TSLA: DTE 14-28, delta ~10, width $10, min credit $0.60
- SPY: DTE 7-21, delta ~15 (puts) / ~10 (calls), width $7, min credit $0.50
- Long legs placed first, full rollback on partial fills

### Key Architecture
- OpenD gateway required (local TCP socket)
- Trade unlock via MD5 password hash
- State with fcntl file locking (concurrent write protection)
- Three data sources working together

### Unique Features
- Multi-leg iron condor with automatic rollback on partial fills
- Per-symbol IC configuration (different params for TSLA vs SPY)
- Triple data source architecture (Moomoo + Tiger + yfinance)

---

## Summary Stats

| Metric | Tiger | IBKR | Longport | Moomoo |
|--------|-------|------|----------|--------|
| **Strategies** | 6 | 1 | 1 | 2 |
| **Broker APIs** | Tiger | IBKR + Tiger | Longport + Tiger | Moomoo + Tiger + yfinance |
| **Account Size** | $319K | $500K+ | $109K | Active (TSLA) |
| **Test Coverage** | 1,025 tests | Minimal | Minimal | None |
| **Dashboard** | Streamlit (18 pages) | None | None | None |
| **Telegram Bot** | Full (63KB) | Basic | Interactive | Notifications only |
| **Maturity** | Production (20+ milestones) | Production | Production | Live testing |
| **Lines of Code** | ~15K+ | ~3K | ~3K | ~2.4K |

---

**Key Insight**: All four systems share the same core patterns — YAML config, JSON state with atomic writes, Telegram notifications, risk checks, scan/manage/status modes. This is the **product pattern** we can generalize.
