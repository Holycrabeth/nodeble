# Cross-Platform Comparison

A feature-by-feature comparison across all 4 proven systems to identify **common patterns** (= product core) vs **broker-specific code** (= plugin layer).

---

## Broker Integration Patterns

| Feature | Tiger | IBKR | Longport | Moomoo |
|---------|-------|------|----------|--------|
| **Connection** | SDK (tigeropen) | ib_async (TCP) | HTTPS API | OpenD gateway (TCP) |
| **Auth** | Tiger ID + RSA key | Port-based (IB Gateway) | App key + JWT token | MD5 password hash |
| **Gateway Required** | No | Yes (IB Gateway/TWS) | No | Yes (OpenD) |
| **Order Types** | Market + Limit | Market + Limit | Limit only | Market + Limit |
| **Multi-leg Orders** | Sequential legs | Sequential legs | Single leg only | Sequential + rollback |
| **Account Currency** | USD | USD | HKD (convert to USD) | USD |
| **Real-time Quotes** | Yes (SDK) | Yes (ib_async) | No (uses Tiger) | Yes (OpenD) |
| **Option Chains** | Yes | Yes | No (uses Tiger) | Yes (but Greeks unreliable) |
| **Greeks** | Yes (reliable) | Yes | No (uses Tiger) | Yes (may be stale) |

### Insight
- Tiger API is the **universal data backbone** — 3 of 4 systems use it for market data
- Execution is broker-specific but follows the same interface: `place_order()`, `get_order()`, `cancel_order()`, `get_positions()`, `get_account_summary()`
- A **Broker Adapter** interface can abstract all 4 brokers behind one API

---

## Strategy Patterns

| Strategy Type | Tiger | IBKR | Longport | Moomoo |
|---------------|-------|------|----------|--------|
| **Cash-Secured Puts** | Theta Harvest | Core strategy | Core strategy | — |
| **Covered Calls** | Theta (wheel) | — | — | CC (TSLA) |
| **Credit Spreads** | Options scanner | — | — | — |
| **Iron Condors** | Condor Factory | — | — | IC (TSLA, SPY) |
| **PMCC / Diagonals** | PMCC strategy | — | — | — |
| **Stock Trend-Following** | Conservative | — | — | — |
| **Stock Mean-Reversion** | Aggressive | — | — | — |

### Insight
- **CSP (Sell Put)** is the most portable strategy — implemented on 3 different brokers
- **Iron Condor** exists on 2 platforms with different approaches (signal-driven vs IV-driven)
- All strategies follow the same lifecycle: **Scan → Execute → Manage → Close/Roll**

---

## Configuration Architecture

| Aspect | Tiger | IBKR | Longport | Moomoo |
|--------|-------|------|----------|--------|
| **Format** | YAML | YAML | YAML | YAML |
| **Strategy Config** | Per-strategy dirs | Single file | Single file | Separate CC + IC files |
| **Risk Config** | Per-strategy risk.yaml | risk.yaml | risk.yaml | risk.yaml |
| **Broker Config** | tiger_config.yaml | ibkr.yaml | longport.yaml | broker.yaml |
| **Notification Config** | In telegram_bot | notify.yaml | notify.yaml | notify.yaml |
| **Kill Switch** | In risk.yaml | In risk.yaml | In risk.yaml | In state.json |

### Common Config Structure (Product Template)
```yaml
# Every system has this shape:
strategy:
  watchlist: [symbols]
  selection: {delta, dte, iv_rank, oi, spread, premium filters}
  management: {profit_target, stop_loss, roll_threshold}

risk:
  kill_switch: bool
  cash_floor: number
  max_contracts: number
  max_per_symbol: number
  max_daily_orders: number
  notional_cap: number

broker:
  connection_params: {...}

notifications:
  telegram: {token, chat_id}
```

---

## State Management

| Aspect | Tiger | IBKR | Longport | Moomoo |
|--------|-------|------|----------|--------|
| **Format** | JSON | JSON | JSON | JSON |
| **Atomic Writes** | tempfile + os.replace | tempfile + os.replace | tempfile + os.replace | fcntl locks |
| **Backup** | Hourly snapshots | None | None | None |
| **Position Tracking** | Per-strategy state files (7) | Single state.json | Single state.json | Single state.json |
| **P&L Tracking** | Per-position + aggregate | Per-position + aggregate | Per-position + aggregate | Per-position + aggregate |
| **Dedup Guard** | Per-strategy | last_scan_date | last_scan_date | last_scan timestamp |

### Common State Shape
```json
{
  "positions": {
    "IDENTIFIER": {
      "underlying": "SPY",
      "expiry": "2026-04-17",
      "strike": 540.0,
      "contracts": 1,
      "entry_premium": 4.50,
      "entry_date": "2026-03-15",
      "entry_delta": -0.15,
      "status": "open",
      "realized_pnl": 0.0
    }
  },
  "total_premium_collected": 5917.0,
  "total_realized_pnl": 384.0
}
```

---

## Risk Framework

| Check | Tiger | IBKR | Longport | Moomoo |
|-------|-------|------|----------|--------|
| **Kill Switch** | Yes | Yes | Yes | Yes |
| **Cash Floor** | Yes ($20K) | Yes ($20K) | Yes ($20K) | No |
| **Max Contracts** | Per-strategy | 10 | 6 | No |
| **Per-Symbol Cap** | Yes | 5 | 3 | No |
| **Daily Order Limit** | Yes | 10 | 3 | No |
| **Portfolio Delta** | Yes | 500 | 150 | No |
| **Notional/NLV Cap** | Yes (1.42x leverage) | 3.0x | 3.0x | No |
| **Stress Test** | 7 scenarios | 20% crash | 20% crash | No |
| **Circuit Breaker** | Daily loss % | No | No | No |
| **Earnings Blackout** | 2d stocks / 7d options | No | No | 2d |
| **Market Hours** | Enforced | Enforced | Enforced | Enforced |
| **Price Guards** | 2-3% deviation | No | No | No |

### Insight
- Tiger has the most comprehensive risk system (production-hardened over 20 milestones)
- **Kill switch** and **market hours** are universal — must be in the product
- Stress testing is a key differentiator — customers will value this

---

## Monitoring & Notifications

| Feature | Tiger | IBKR | Longport | Moomoo |
|---------|-------|------|----------|--------|
| **Telegram Bot** | Full (commands + alerts) | Commands + alerts | Commands + alerts | Alerts only |
| **Dashboard** | Streamlit (18 pages) | None | None | None |
| **Audit Trail** | JSON audit log | Execution logs | Execution logs | File logs |
| **Health Checks** | Automated (6 offline + 2 live) | None | None | None |
| **Greeks Monitoring** | Portfolio-level aggregation | None | None | None |
| **Risk Reports** | Stress test + VaR | None | None | None |

---

## Automation & Scheduling

| Aspect | Tiger | IBKR | Longport | Moomoo |
|--------|-------|------|----------|--------|
| **Scheduler** | launchd (15 plists) | Manual/cron | cron (run.sh wrapper) | Manual |
| **Job Count** | 15 daily jobs | ~3-4 | ~3-4 | Manual runs |
| **Dry-run** | All jobs | All modes | All modes | All modes |
| **CLI Args** | --strategy, --mode | --mode, --dry-run, --force | --mode, --dry-run, --force | subcommand, --execute, --dry-run |

---

## Common Patterns = Product Core

These patterns appear in ALL or MOST systems and form the **universal product layer**:

1. **Scan / Manage / Status lifecycle** — every strategy follows this
2. **YAML-driven configuration** — code-free parameter tuning
3. **JSON state with atomic persistence** — crash-safe position tracking
4. **Broker adapter pattern** — unified interface, broker-specific implementation
5. **Risk check pipeline** — sequential fail-closed checks before any trade
6. **Telegram notifications** — real-time alerts on actions and errors
7. **Kill switch** — emergency halt accessible remotely
8. **Dry-run mode** — test without real capital
9. **Position lifecycle** — pending → open → closing → closed/rolled/expired
10. **Dedup guards** — prevent duplicate orders from retries/crons

## Broker-Specific = Plugin Layer

These are broker-specific and should be **plugins**, not core:

1. **API connection handling** (SDK, gateway, HTTPS)
2. **Authentication** (RSA keys, tokens, passwords)
3. **Order format** (OCC codes, contract specs)
4. **Account data** (currency conversion, margin calc)
5. **Option chain retrieval** (different APIs, different formats)
6. **Greeks sourcing** (reliability varies by broker)
