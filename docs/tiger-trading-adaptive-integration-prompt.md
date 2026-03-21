# Prompt: Integrate Adaptive Iron Condor Layer into tiger-trading

## Context

We built an adaptive parameter computation layer for iron condor trading in the NODEBLE project. It's a pure function that computes optimal delta ranges and DTE based on:
1. **Directional skew** from the 20 trend-following indicators (which tiger-trading already has)
2. **VIX regime scaling** (tiger-trading already has `data/vix.py`)

The adaptive layer sits between config and the condor factory. It reads market conditions and adjusts deltas/DTE automatically instead of using static config values.

## What You Need to Do

### Step 1: Copy the adaptive module

Copy this single file into tiger-trading. It has ZERO external dependencies — only uses Python stdlib `logging`.

**Source:** `/home/mayongtao/projects/nodeble/src/nodeble/strategy/adaptive.py`

**Destination suggestion:** `condor/adaptive.py` (next to `condor/factory.py`)

The file contains two internal functions and one public function:

```python
def compute_adaptive_params(
    bull_share: float,      # from VotingEngine (0.0 = strongly bearish, 1.0 = strongly bullish)
    vix: float | None,      # from data/vix.py get_vix()
    base_config: dict,      # the selection section from config_condor/strategy.yaml
    adaptive_config: dict,  # new adaptive section (see below)
) -> dict:
    """Returns adjusted put/call delta ranges and DTE range."""
```

The function:
- Takes VIX → looks up a tier → gets a delta multiplier and DTE range
- Takes bull_share → computes directional skew (bearish = tighten put delta, loosen call delta)
- Applies both to the base config's delta_min/max values
- Returns a dict with: `put_delta_min`, `put_delta_max`, `call_delta_min`, `call_delta_max`, `dte_min`, `dte_max`, `dte_ideal`

### Step 2: Add config section to `config_condor/strategy.yaml`

Add this section:

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

**How VIX tiers work:**
- VIX ≤ 15 (calm): multiply base delta by 1.50 (more aggressive), use DTE 15-30
- VIX 15-20 (standard): delta unchanged, DTE 12-25
- VIX 20-25 (defensive): multiply by 0.85, DTE 7-20
- VIX 25+ (most defensive): multiply by 0.70, DTE 3-15

**How skew works:**
- bull_share in neutral zone (0.45-0.55): symmetric deltas, no skew
- bull_share < 0.45 (bearish): tighten put delta (lower), loosen call delta (higher)
- bull_share > 0.55 (bullish): opposite
- bull_share ≤ 0.30 or ≥ 0.70: maximum skew clamped at ±25% of base delta

### Step 3: Integrate into `run_condor_job.py`

The integration point is in `run_condor_job.py` (or wherever `scan_for_condors()` is called). BEFORE calling the factory, compute adaptive params and overwrite the selection config.

tiger-trading already runs signals daily at 17:00 ET via `run_signal_job.py --strategy conservative`. The conservative signal produces a `VoteResult` with `bull_share` per symbol. You can either:

**Option A: Use the existing signal state files**
Read the latest signal file from `data/signals/` to get bull_share per symbol, then average across the condor watchlist.

**Option B: Run indicators inline**
Since `run_condor_job.py` runs at 09:50 ET (market hours), you could run the 20 conservative indicators on-the-fly using the DataFetcher. But this is slower and redundant since signals already ran at 17:00 the previous day.

**Recommended: Option A.** The signal files are already there. Example integration:

```python
# In run_condor_job.py, before calling scan_for_condors():

import json
import glob
from data.vix import get_vix
from condor.adaptive import compute_adaptive_params

# 1. Read latest signal file
signal_files = sorted(glob.glob("data/signals/signal_*.json"))
bull_shares = []
if signal_files:
    with open(signal_files[-1]) as f:
        signals = json.load(f)
    # signals is a list of dicts, or a dict — check your signal file format
    # Extract bull_share for condor watchlist symbols
    condor_watchlist = strategy_cfg.get("watchlist", [])
    for sig in signals:  # adapt to your actual signal file structure
        if sig.get("symbol") in condor_watchlist:
            bull_shares.append(sig.get("bull_share", 0.5))

avg_bull_share = sum(bull_shares) / len(bull_shares) if bull_shares else 0.50

# 2. Get VIX
vix = get_vix()

# 3. Compute adaptive params
adaptive_cfg = strategy_cfg.get("adaptive", {})
if adaptive_cfg:
    sel = strategy_cfg.get("selection", {})
    adjusted = compute_adaptive_params(avg_bull_share, vix, sel, adaptive_cfg)
    strategy_cfg["selection"].update(adjusted)
    logger.info(
        f"Adaptive params: VIX={vix}, bull_share={avg_bull_share:.2f}, "
        f"put_delta=[{adjusted['put_delta_min']:.3f}-{adjusted['put_delta_max']:.3f}], "
        f"call_delta=[{adjusted['call_delta_min']:.3f}-{adjusted['call_delta_max']:.3f}], "
        f"DTE=[{adjusted['dte_min']}-{adjusted['dte_max']}]"
    )

# 4. Call factory as usual — it reads the (now-adjusted) selection config
candidates, rejections = scan_for_condors(broker, state, risk_cfg, strategy_cfg, dry_run)
```

**IMPORTANT:** You need to adapt the signal file reading to match tiger-trading's actual signal file format. The signal files are JSON, written by `run_signal_job.py`. Check the structure — it might be a list of VoteResult dicts or a different format. The key field you need is `bull_share` per symbol.

### Step 4: Remove old VIX scaling from factory

tiger-trading's `condor/factory.py` has VIX scaling code that is currently disabled (`vix_scaling.enabled: false` in config). Since the adaptive layer handles VIX scaling upstream, you can either:
- Remove the old `vix_scaling` block from `factory.py`
- Or leave it disabled — it won't interfere since `enabled: false`

### Step 5: Test

The adaptive module has its own test file you can copy:

**Source:** `/home/mayongtao/projects/nodeble/tests/test_adaptive.py`

Copy it and adjust imports from `nodeble.strategy.adaptive` → `condor.adaptive` (or wherever you put it).

Key test cases:
- VIX ≤ 15 → delta scaled up by 1.5, DTE 15-30
- VIX 25+ → delta scaled down by 0.7, DTE 3-15
- VIX None → falls to 15-20 tier (fail-to-middle)
- bull_share 0.50 → symmetric deltas
- bull_share 0.35 → bearish skew (put delta lower, call delta higher)
- bull_share 0.25 → maximum skew clamped

## What NOT to Change

- Do NOT modify the 20 indicators or VotingEngine — they're already working
- Do NOT change the factory's internal logic — it just reads `selection` config as before
- Do NOT touch the signal pipeline — just read its output files
- The adaptive layer is ADDITIVE — if something goes wrong, just remove the `adaptive` section from config and everything reverts to static behavior

## Key Design Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| VIX unavailable | Fall to 15-20 tier | Not most aggressive, not blocked |
| Strongly directional (bull_share ≤0.30 or ≥0.70) | Still trade IC, max skew | Always trade, never skip |
| Neutral zone (0.45-0.55) | Symmetric deltas | No edge to skew on |
| Position sizing | NOT adaptive | Only delta + DTE are adaptive |
| DTE ranges | Short (3-30) | SPY/QQQ/IWM have daily/weekly expirations |

## Files to Reference

- **Adaptive module:** `/home/mayongtao/projects/nodeble/src/nodeble/strategy/adaptive.py`
- **Tests:** `/home/mayongtao/projects/nodeble/tests/test_adaptive.py`
- **Design spec (full context):** `/home/mayongtao/projects/nodeble/docs/superpowers/specs/2026-03-21-adaptive-strategy-design.md`
