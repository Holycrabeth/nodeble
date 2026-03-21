# VIX Term Structure Gate & Dynamic Profit Targets — Design Spec

## Goal

Add two improvements to the adaptive IC engine:
1. **VIX term structure gate** — use VIX9D/VIX ratio to detect backwardation and further reduce delta/DTE when near-term vol is elevated
2. **Dynamic profit targets** — adjust profit-take percentage based on current VIX regime instead of a fixed 50%

## Problem

The current adaptive layer uses VIX level alone to scale parameters. But VIX level doesn't distinguish between "VIX is high and stabilizing" (contango, safe to sell) vs "VIX is high and accelerating" (backwardation, danger). The term structure ratio captures this distinction.

Similarly, a fixed 50% profit target ignores that rich-premium environments (high VIX) warrant holding longer, while thin-premium environments (low VIX) warrant taking profits quickly.

## Improvement 1: VIX Term Structure Gate

### Data Source

Fetch VIX9D (9-day implied volatility) from yfinance (`^VIX9D`) alongside the existing VIX fetch. VIX9D reacts faster than VIX to near-term stress, making the ratio a leading indicator of trouble.

### Term Ratio

```
term_ratio = VIX9D / VIX
```

- `term_ratio < 1.0` → **contango** (normal). Near-term vol lower than long-term. Safe environment for selling premium.
- `term_ratio > 1.0` → **backwardation**. Near-term vol spiking above long-term. Market stress — reduce exposure.

### Effect on Adaptive Parameters (Soft Gate)

The term structure scaling stacks multiplicatively on top of the existing VIX tier scaling. It never blocks trading — it reduces delta and shortens DTE proportionally to how inverted the curve is.

| term_ratio | Tier Name | Delta Multiplier | DTE Reduction |
|------------|-----------|-----------------|---------------|
| ≤ 1.00 | contango | 1.00 (no change) | 0% |
| 1.00-1.05 | mild_backwardation | 0.90 (-10%) | 15% shorter |
| 1.05-1.10 | moderate_backwardation | 0.80 (-20%) | 30% shorter |
| > 1.10 | severe_backwardation | 0.65 (-35%) | 50% shorter |

**Combined example:** VIX = 28 (VIX tier delta_scale = 0.70), term_ratio = 1.08 (moderate backwardation, multiplier = 0.80).
Combined delta multiplier = `0.70 × 0.80 = 0.56`. Base delta 0.15 → effective delta 0.084.

**DTE reduction:** Applied to the VIX tier's DTE range. For VIX 25+ tier (DTE 3-15) with 30% reduction:
- `dte_min = max(1, round(3 * 0.70)) = 2`
- `dte_max = round(15 * 0.70) = 10`

### Implementation: `adaptive.py`

The `compute_adaptive_params()` function gains a new parameter `term_ratio`:

```python
def compute_adaptive_params(
    bull_share: float,
    vix: float | None,
    base_config: dict,
    adaptive_config: dict,
    term_ratio: float | None = None,  # NEW
) -> dict:
```

After computing VIX-tier delta_scale and before applying directional skew, apply the term structure multiplier:

```python
term_cfg = adaptive_config.get("term_structure", {})
term_tiers = term_cfg.get("tiers", DEFAULT_TERM_TIERS)
term_multiplier, dte_reduction = _get_term_structure_adjustment(term_ratio, term_tiers)
delta_scale *= term_multiplier
dte_min = max(1, round(dte_min * (1 - dte_reduction)))
dte_max = round(dte_max * (1 - dte_reduction))
```

### Implementation: `data/vix.py`

Add `get_vix9d()` function, identical pattern to existing `get_vix()`:

```python
def get_vix9d() -> float | None:
    """Fetch current VIX9D (9-day implied vol). Returns None on failure."""
    # Same pattern as get_vix() but with ticker "^VIX9D"
```

### Implementation: `signals/signal_job.py`

The signal job fetches VIX9D alongside VIX and stores both in `signal_state.json`:

```json
{
  "version": 2,
  "generated_at": "2026-03-21T09:30:00-04:00",
  "vix": 28.0,
  "vix9d": 31.5,
  "term_ratio": 1.125,
  "term_structure": "severe_backwardation",
  "vix_fallback": false,
  "symbols": { ... }
}
```

### Implementation: `__main__.py`

The scan mode reads `term_ratio` from signal state and passes it to `compute_adaptive_params()`.

### Config (`strategy.yaml`)

```yaml
adaptive:
  # ... existing vix_tiers and skew sections ...

  term_structure:
    tiers:
      - { max_ratio: 1.00, delta_multiplier: 1.00, dte_reduction: 0.00 }
      - { max_ratio: 1.05, delta_multiplier: 0.90, dte_reduction: 0.15 }
      - { max_ratio: 1.10, delta_multiplier: 0.80, dte_reduction: 0.30 }
      - { max_ratio: 999,  delta_multiplier: 0.65, dte_reduction: 0.50 }
```

### Failure Mode

VIX9D fetch fails → `term_ratio = None` → treat as contango (no additional reduction). Log WARNING + Telegram alert: `"WARNING: VIX9D unavailable, term structure gate disabled for this run."`

### Logging

Every run logs:
- `"VIX9D fetch: {value}"` or `"VIX9D fetch failed: {error}"`
- `"Term ratio: {ratio:.3f} → {tier_name} (delta ×{multiplier}, DTE -{reduction}%)"`
- `"Combined adaptive params: VIX delta_scale={x} × term_multiplier={y} = {combined}"`

### Telegram

Signal job summary includes term structure:
```
Signal Update (VIX 28.0, VIX9D 31.5, backwardation 1.12x):
SPY: bearish (bull 35%, 7/20)
QQQ: bullish (bull 62%, 12/20)
```

---

## Improvement 2: Dynamic Profit Targets

### Current Behavior

The manage job reads a fixed `profit_take_pct: 0.50` from `strategy.yaml` management section. When a position's P&L reaches 50% of max credit, it closes.

### New Behavior

The manage job fetches current VIX (live, not entry-time) and looks up a profit target from configurable tiers:

| Current VIX | profit_take_pct | Reasoning |
|-------------|----------------|-----------|
| ≤ 15 | 0.40 | Premium thin, take what you can |
| 15-20 | 0.50 | Standard, proven |
| 20-25 | 0.60 | Richer premium, hold a bit longer |
| 25+ | 0.75 | Very rich, worth holding |

### Config (`strategy.yaml`)

```yaml
management:
  max_risk_per_trade: 2000
  stop_loss_pct: 2.0
  close_before_dte: 3

  dynamic_profit_targets:
    - { max_vix: 15,  profit_take_pct: 0.40 }
    - { max_vix: 20,  profit_take_pct: 0.50 }
    - { max_vix: 25,  profit_take_pct: 0.60 }
    - { max_vix: 999, profit_take_pct: 0.75 }
```

**Backward compatibility:** If `dynamic_profit_targets` is absent, fall back to the static `profit_take_pct` value (default 0.50).

### Implementation: `strategy/manager.py`

In `evaluate_positions()`, before checking each position's P&L against the profit target:

```python
from nodeble.data.vix import get_vix

def _get_dynamic_profit_target(strategy_cfg: dict, vix: float | None) -> float:
    """Look up profit target based on current VIX.

    VIX is fetched once in __main__.py and passed in to keep manager side-effect-free.
    """
    mgmt = strategy_cfg.get("management", {})
    dynamic = mgmt.get("dynamic_profit_targets")

    if not dynamic:
        return mgmt.get("profit_take_pct", 0.50)

    if vix is None:
        logger.warning("VIX unavailable for dynamic profit target, using 0.50 fallback")
        return 0.50

    for tier in sorted(dynamic, key=lambda t: t["max_vix"]):
        if vix <= tier["max_vix"]:
            logger.info(f"Dynamic profit target: VIX={vix:.1f}, using {tier['profit_take_pct']:.0%} (tier ≤{tier['max_vix']})")
            return tier["profit_take_pct"]

    return 0.50
```

### DTE Close Rule

**Unchanged.** Keep `close_before_dte: 3` as is. Theta decay works in the seller's favor — closing early sacrifices the acceleration of decay near expiration. The dynamic profit target handles the "when to take profit" question; the DTE close rule is only for positions that haven't hit their target and need to be closed for expiration safety.

### Failure Mode

VIX fetch fails during manage → use 0.50 (standard) as fallback. Log WARNING + Telegram alert.

### Logging

Every position evaluation logs:
- `"Dynamic profit target: VIX={vix}, using {pct}% (tier {tier_name})"`
- `"Position {symbol} P&L {pnl_pct}% vs target {target_pct}% → {action}"`

---

## Files Affected

### Modified

| File | Change |
|------|--------|
| `src/nodeble/data/vix.py` | Add `get_vix9d()` function |
| `src/nodeble/strategy/adaptive.py` | Add `term_ratio` parameter, term structure scaling logic |
| `src/nodeble/strategy/manager.py` | Add `_get_dynamic_profit_target()`, use in `evaluate_positions()` |
| `src/nodeble/signals/signal_job.py` | Fetch VIX9D, compute term_ratio, store in signal state |
| `src/nodeble/__main__.py` | Pass term_ratio to `compute_adaptive_params()` |
| `config/strategy.yaml.example` | Add `term_structure` and `dynamic_profit_targets` sections |

### New

| File | Purpose |
|------|---------|
| `tests/test_term_structure.py` | Tests for VIX9D fetch, term ratio tiers, combined scaling |
| `tests/test_dynamic_targets.py` | Tests for dynamic profit target lookup |

---

## Testing Strategy

### Unit tests — term structure

- term_ratio 0.95 (contango) → no additional reduction
- term_ratio 1.03 (mild backwardation) → delta ×0.90, DTE -15%
- term_ratio 1.08 (moderate) → delta ×0.80, DTE -30%
- term_ratio 1.15 (severe) → delta ×0.65, DTE -50%
- term_ratio None (fetch failed) → no reduction, log warning
- Combined with existing VIX scaling: multiplicative, not additive
- DTE minimum floor of 1 (never go to 0)

### Unit tests — dynamic profit targets

- VIX 12 → profit target 40%
- VIX 18 → profit target 50%
- VIX 22 → profit target 60%
- VIX 30 → profit target 75%
- VIX None → fallback to 50%
- No dynamic_profit_targets in config → fallback to static profit_take_pct
- Backward compatibility: old config without dynamic section still works

---

## Dependencies

No new Python dependencies. yfinance (already present) handles VIX9D data.
