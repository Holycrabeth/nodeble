# Adaptive Iron Condor Strategy Engine — Design Spec

## Goal

Replace the static config-driven IC parameter selection with a two-layer adaptive system that automatically computes optimal deltas and DTE based on market conditions (directional indicators + VIX regime).

## Problem

The current IC factory uses fixed delta ranges and DTE from the user's `strategy.yaml`. A bearish market gets the same symmetric 0.20/0.20 delta as a bullish market. This is naive — the system should read market conditions and adjust automatically.

## Architecture

Standalone adaptive layer (`strategy/adaptive.py`) sits between config and the IC factory. Pure function: signal + VIX + base config → adjusted parameters. Factory code stays untouched.

**Integration point:** The caller (`__main__.py`) reads `signal_state.json`, calls `compute_adaptive_params()`, and overwrites the `strategy_cfg["selection"]` dict with the adaptive output (put/call delta ranges, DTE range) before passing it to `scan_for_condors()`. The factory reads `sel = strategy_cfg.get("selection", {})` as it does today — no factory changes needed. The existing `vix_scaling` code path in the factory (lines 107-112) is removed since VIX scaling is now handled by the adaptive layer upstream.

```
Daily signal job (9:30 AM ET)
├── Fetch 252-day OHLCV per symbol (yfinance)
├── Run 20 trend-following indicators → VotingEngine → bull_share per symbol
├── Fetch VIX (yfinance)
└── Write ~/.nodeble/data/signal_state.json

IC scan job (10:00 AM ET)
├── Read signal_state.json
├── adaptive.py: compute adjusted deltas + DTE
│   Input:  bull_share, VIX, base config
│   Output: put_delta_min/max, call_delta_min/max, dte_min/max/ideal
├── Caller overwrites strategy_cfg["selection"] with adaptive output
└── Factory uses adjusted params for strike selection (factory code untouched)

Manage jobs (10:30 AM, 3:00 PM ET) — unchanged
```

## Layer 1: Directional Skew (20 Indicator Voting System)

### Indicators

Extract the 20 trend-following indicators from `reference/tiger-trading/`:

**Trend (5):** SMA Cross, EMA Cross, ADX Trend, Supertrend, Aroon Oscillator
**Momentum (5):** RSI, MACD Histogram, Stochastic Oscillator, CCI, Williams %R
**Volatility (5):** Bollinger Band Position, Keltner Channel, ATR Trend, Donchian Channel, Bollinger Band Width
**Volume (5):** OBV Trend, MFI, CMF, VWAP Distance, Volume SMA Ratio

Adaptive RSI is enabled (16.9% backtest improvement). All other adaptive indicator variants remain disabled.

### NOT Extracted

- Mean-reversion indicators (aggressive strategy) — not relevant for IC
- Sentiment indicators — 81.9% return drag in testing
- WeightedVotingEngine — unnecessary complexity
- Allocator/positioning logic — IC has its own sizing

### VotingEngine (4-Gate Quorum System)

Each indicator casts a vote: +1 (bullish), 0 (neutral), -1 (bearish).

**Gate 1 — Active Signal:** At least 1 indicator must have a non-neutral vote.
**Gate 2 — Quorum:** At least 35% (7/20) of indicators must be active.
**Gate 3 — Category Diversity:** At least 3 of 4 categories must have active votes (trend, momentum, volatility, volume — sentiment is not extracted).
**Gate 4 — Deadband:** bull_share within ±6% of 0.50 (i.e., 0.44–0.56) is treated as noise → HOLD.

Output: `bull_share` (0.0 to 1.0) per symbol.

### Skew Rules

- `bull_share` 0.45–0.55 (neutral zone): **symmetric deltas**, no skew applied
- `bull_share` < 0.45 (bearish): tighten put delta (lower), loosen call delta (higher), proportional to distance from 0.50
- `bull_share` > 0.55 (bullish): opposite — tighten call delta, loosen put delta
- `bull_share` < 0.30 or > 0.70 (strongly directional): **maximum skew** applied, but still trade the IC (never skip)

**Moderate skew example (bull_share = 0.30, bearish):**
- Base delta 0.20 → put delta 0.15, call delta 0.25

Maximum skew ratio: ±25% of base delta (configurable in `strategy.yaml`).

## Layer 2: VIX Regime Scaling

VIX level determines the base delta multiplier and DTE range:

| VIX Range | delta_scale | DTE Range | Posture |
|-----------|-------------|-----------|---------|
| ≤ 15      | 1.50        | 15–30     | Aggressive (calm market, collect more premium) |
| 15–20     | 1.00        | 12–25     | Standard |
| 20–25     | 0.85        | 7–20      | Defensive |
| 25+       | 0.70        | 3–15      | Most defensive (short duration, minimize exposure) |

Short DTE ranges are viable because the target watchlist (SPY, QQQ, IWM) has daily/weekly expirations with strong liquidity.

## Combined Formula

```
1. VIX tier → base_delta_scaled = config.put_delta * vix_tier.delta_scale
2. Directional skew → put_delta = base_delta_scaled * (1 - skew_adjustment)
                       call_delta = base_delta_scaled * (1 + skew_adjustment)
3. DTE range from VIX tier (dte_ideal = midpoint of tier's dte_min and dte_max)

Apply steps 1-2 to both _min and _max independently (e.g., put_delta_min and put_delta_max
are each scaled by VIX and skewed by direction).
```

Where `skew_adjustment` is 0.0 in the neutral zone, scaling linearly to `max_skew_ratio` (0.25) at the extremes.

## Adaptive Module Interface

```python
# src/nodeble/strategy/adaptive.py

def compute_adaptive_params(
    bull_share: float,      # from signal_state.json (0.0 to 1.0)
    vix: float | None,      # from signal_state.json
    base_config: dict,      # user's strategy.yaml selection section
    adaptive_config: dict,  # user's strategy.yaml adaptive section
) -> dict:
    """Compute VIX-scaled, direction-skewed parameters.

    Returns:
        {
            "put_delta_min": float,
            "put_delta_max": float,
            "call_delta_min": float,
            "call_delta_max": float,
            "dte_min": int,
            "dte_max": int,
            "dte_ideal": int,  # midpoint of tier's DTE range
        }
    """
```

## Signal State File

Written to `~/.nodeble/data/signal_state.json` by the signal job. Atomic writes (tempfile + `os.replace()`).

```json
{
  "version": 1,
  "generated_at": "2026-03-21T09:30:00-04:00",
  "vix": 18.5,
  "vix_tier": "15-20",
  "vix_fallback": false,
  "symbols": {
    "SPY": {
      "bull_share": 0.35,
      "decision": "SELL",
      "confidence": 0.30,
      "bull_count": 7,
      "bear_count": 13,
      "active_count": 20,
      "active_ratio": 1.0,
      "votes": {
        "sma_cross": -1,
        "ema_cross": -1,
        "rsi": 0,
        "macd_histogram": -1
      }
    }
  }
}
```

## Failure Modes

| Failure | Behavior | Logging |
|---------|----------|---------|
| Signal file missing | Use VIX 15-20 fallback, symmetric deltas | WARNING log + Telegram alert |
| Signal file stale (>24h) | Same as missing | WARNING log + Telegram alert |
| VIX unavailable (null in file) | Use VIX 15-20 tier | WARNING log + Telegram alert |
| yfinance OHLCV fetch fails for a symbol | Skip that symbol's signal, log error | WARNING log per symbol |
| All indicators neutral for a symbol | bull_share = 0.50, symmetric deltas | INFO log (normal condition) |

In all failure cases, the system continues trading with safe defaults — never blocks entirely.

## Config Changes

The `strategy.yaml` gains an `adaptive` section. Adaptive is always on — no enable/disable flag.

```yaml
adaptive:
  vix_tiers:
    - { max_vix: 15,  delta_scale: 1.50, dte_min: 15, dte_max: 30 }
    - { max_vix: 20,  delta_scale: 1.00, dte_min: 12, dte_max: 25 }
    - { max_vix: 25,  delta_scale: 0.85, dte_min: 7,  dte_max: 20 }
    - { max_vix: 999, delta_scale: 0.70, dte_min: 3,  dte_max: 15 }

  skew:
    neutral_zone: [0.45, 0.55]
    max_skew_ratio: 0.25
```

The existing `vix_scaling` section is replaced by this. The existing `selection` section remains and serves as the base values that the adaptive layer adjusts.

Position sizing (`sizing`, `management.max_risk_per_trade`) stays fixed in user config — the adaptive layer only controls delta and DTE.

## New Files

### Extract from tiger-trading

| Source | Destination | Notes |
|--------|-------------|-------|
| `indicators/base.py` | `src/nodeble/signals/base.py` | BaseIndicator abstract class |
| `indicators/trend.py` | `src/nodeble/signals/trend.py` | 5 trend indicators |
| `indicators/momentum.py` | `src/nodeble/signals/momentum.py` | 5 momentum indicators |
| `indicators/volatility.py` | `src/nodeble/signals/volatility.py` | 5 volatility indicators |
| `indicators/volume.py` | `src/nodeble/signals/volume.py` | 5 volume indicators |
| `indicators/volume_filter.py` | `src/nodeble/signals/volume_filter.py` | Volume noise filtering utility (imported by volume.py) |
| `indicators/registry.py` | `src/nodeble/signals/registry.py` | Builds 20-indicator list |
| `engine/scorer.py` | `src/nodeble/signals/scorer.py` | VotingEngine (4-gate) |

### New files to create

| File | Purpose |
|------|---------|
| `src/nodeble/signals/__init__.py` | Package init |
| `src/nodeble/signals/signal_job.py` | Entry point: fetch OHLCV, run indicators, fetch VIX, write state |
| `src/nodeble/strategy/adaptive.py` | Pure function: signal + VIX + config → adjusted params |
| `config/signals.yaml.example` | Voting thresholds, indicator evolution flags (see below) |

### signals.yaml.example skeleton

```yaml
voting:
  implemented_indicators: 20
  min_active_ratio: 0.35
  min_active_categories: 3
  deadband: 0.06
  buy_threshold: 0.58
  strong_buy_threshold: 0.70
  sell_threshold: 0.58
  strong_sell_threshold: 0.70

indicator_evolution:
  adaptive_rsi:
    enabled: true
    lookback: 252
    pctile_low: 10.0
    pctile_high: 90.0
    floor_low: 20.0
    ceil_high: 80.0
```

## Cron Schedule

```
# NODEBLE signal — weekdays 9:30 AM ET
30 9 * * 1-5 cd $NODEBLE_DIR && .venv/bin/python -m nodeble --mode signal >> $NODEBLE_DATA/logs/cron.log 2>&1

# NODEBLE scan — weekdays 10:00 AM ET
0 10 * * 1-5 cd $NODEBLE_DIR && .venv/bin/python -m nodeble --mode scan >> $NODEBLE_DATA/logs/cron.log 2>&1

# NODEBLE manage — weekdays 10:30 AM and 3:00 PM ET
30 10 * * 1-5 cd $NODEBLE_DIR && .venv/bin/python -m nodeble --mode manage >> $NODEBLE_DATA/logs/cron.log 2>&1
0 15 * * 1-5 cd $NODEBLE_DIR && .venv/bin/python -m nodeble --mode manage --force >> $NODEBLE_DATA/logs/cron.log 2>&1
```

CLI entry: `.venv/bin/python -m nodeble --mode signal`

## Telegram Notifications

**Signal job completion:**
```
Signal Update (VIX 18.5):
SPY: bearish (bull 35%, 7/20)
QQQ: bullish (bull 62%, 12/20)
IWM: neutral (bull 48%, 10/20)
```

**Signal fallback warning:**
```
WARNING: Signal data unavailable, IC scan using fallback defaults. Check signal job.
```

## Testing Strategy

### Unit tests — adaptive.py
- VIX ≤ 15 → delta scaled up by 1.5, DTE 15-30
- VIX 25+ → delta scaled down by 0.7, DTE 3-15
- VIX unavailable → falls to 15-20 tier
- bull_share 0.50 → symmetric deltas
- bull_share 0.35 → put delta lower, call delta higher (bearish skew)
- bull_share 0.70 → opposite skew (bullish)
- bull_share 0.25 → maximum skew applied

### Unit tests — signal job
- 20 indicators produce correct vote count
- VotingEngine 4 gates work correctly
- Signal state file written with correct structure
- Stale signal detection (>24h → warning + Telegram + fallback)

### Integration test
- Signal job writes file → IC scanner reads it → adaptive params flow into factory → correct strikes selected

### Not re-tested
- Individual indicators — already have 1025 tests in tiger-trading
- Factory/executor/manager — already have 96 tests in nodeble

## Dependencies

New Python dependencies:
- `pandas` — already present (used by indicators for DataFrame operations)
- `numpy` — already present transitively via pandas (used directly by volume indicators)
- `ta` or manual computation — indicators use pandas operations directly, no external TA library needed

No new external dependencies required. yfinance (already present) handles all data fetching.
