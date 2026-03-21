# VIX Term Structure Gate & Dynamic Profit Targets — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add VIX9D/VIX term structure scaling to the adaptive entry layer and VIX-regime-aware dynamic profit targets to position management.

**Architecture:** The term structure gate stacks multiplicatively on top of the existing VIX tier scaling in `adaptive.py`. The dynamic profit targets replace the fixed `profit_take_pct` in `manager.py` with a VIX-tier lookup. Both use existing `data/vix.py` for data.

**Tech Stack:** Python 3.12+, yfinance, pytest

**Spec:** `docs/superpowers/specs/2026-03-21-vix-term-structure-and-dynamic-targets-design.md`

---

## File Structure

### Modified

| File | Change |
|------|--------|
| `src/nodeble/data/vix.py` | Add `get_vix9d()` function |
| `src/nodeble/strategy/adaptive.py` | Add `term_ratio` param, term structure scaling |
| `src/nodeble/strategy/manager.py` | Add `_get_dynamic_profit_target()`, use in `evaluate_positions()` |
| `src/nodeble/signals/signal_job.py` | Fetch VIX9D, compute term_ratio, store in signal state |
| `src/nodeble/__main__.py` | Pass term_ratio to adaptive, fetch VIX for manage mode |
| `config/strategy.yaml.example` | Add `term_structure` and `dynamic_profit_targets` sections |
| `tests/test_adaptive.py` | Add term structure tests |

### New

| File | Purpose |
|------|---------|
| `tests/test_dynamic_targets.py` | Tests for dynamic profit target lookup |

---

### Task 1: Add `get_vix9d()` to data/vix.py

**Files:**
- Modify: `src/nodeble/data/vix.py`

- [ ] **Step 1: Add get_vix9d function**

Add after the existing `get_vix()` function at line 29:

```python
def get_vix9d() -> float | None:
    """Fetch current VIX9D (9-day implied vol). Returns None on failure."""
    try:
        ticker = yf.Ticker("^VIX9D")
        try:
            price = ticker.fast_info.last_price
            if price and price > 0:
                return float(price)
        except Exception:
            pass

        hist = ticker.history(period="1d")
        if hist is not None and not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception as e:
        logger.warning(f"Failed to fetch VIX9D: {e}")

    return None
```

- [ ] **Step 2: Verify it works**

Run: `cd /home/mayongtao/projects/nodeble && .venv/bin/python -c "from nodeble.data.vix import get_vix9d; print(f'VIX9D: {get_vix9d()}')"`
Expected: `VIX9D: <number>`

- [ ] **Step 3: Commit**

```bash
git add src/nodeble/data/vix.py
git commit -m "feat: add get_vix9d() for term structure calculation"
```

---

### Task 2: Add term structure scaling to adaptive.py

**Files:**
- Modify: `src/nodeble/strategy/adaptive.py`
- Modify: `tests/test_adaptive.py`

- [ ] **Step 1: Write failing tests for term structure**

Add to the end of `tests/test_adaptive.py`:

```python
# --- Term structure tests ---

def test_term_contango_no_change():
    """term_ratio 0.95 (contango) -> no additional reduction."""
    result = compute_adaptive_params(
        bull_share=0.50, vix=18.0, base_config=BASE_CFG,
        adaptive_config=ADAPTIVE_CFG, term_ratio=0.95,
    )
    # VIX 15-20 tier, delta_scale 1.00, no term reduction
    assert abs(result["put_delta_max"] - 0.15) < 0.001
    assert result["dte_min"] == 12
    assert result["dte_max"] == 25


def test_term_mild_backwardation():
    """term_ratio 1.03 -> delta x0.90, DTE -15%."""
    result = compute_adaptive_params(
        bull_share=0.50, vix=18.0, base_config=BASE_CFG,
        adaptive_config=ADAPTIVE_CFG, term_ratio=1.03,
    )
    # Base 0.15 * 1.00 (VIX) * 0.90 (term) = 0.135
    assert abs(result["put_delta_max"] - 0.135) < 0.001
    # DTE: 12 * 0.85 = 10, 25 * 0.85 = 21
    assert result["dte_min"] == 10
    assert result["dte_max"] == 21


def test_term_moderate_backwardation():
    """term_ratio 1.08 -> delta x0.80, DTE -30%."""
    result = compute_adaptive_params(
        bull_share=0.50, vix=18.0, base_config=BASE_CFG,
        adaptive_config=ADAPTIVE_CFG, term_ratio=1.08,
    )
    # Base 0.15 * 1.00 * 0.80 = 0.12
    assert abs(result["put_delta_max"] - 0.12) < 0.001
    # DTE: 12 * 0.70 = 8, 25 * 0.70 = 18
    assert result["dte_min"] == 8
    assert result["dte_max"] == 18


def test_term_severe_backwardation():
    """term_ratio 1.15 -> delta x0.65, DTE -50%."""
    result = compute_adaptive_params(
        bull_share=0.50, vix=18.0, base_config=BASE_CFG,
        adaptive_config=ADAPTIVE_CFG, term_ratio=1.15,
    )
    # Base 0.15 * 1.00 * 0.65 = 0.0975
    assert abs(result["put_delta_max"] - 0.0975) < 0.001
    # DTE: 12 * 0.50 = 6, 25 * 0.50 = 12 (with rounding)
    assert result["dte_min"] == 6
    assert result["dte_max"] == 12


def test_term_ratio_none_no_change():
    """term_ratio None -> treat as contango, no reduction."""
    result = compute_adaptive_params(
        bull_share=0.50, vix=18.0, base_config=BASE_CFG,
        adaptive_config=ADAPTIVE_CFG, term_ratio=None,
    )
    assert abs(result["put_delta_max"] - 0.15) < 0.001
    assert result["dte_min"] == 12


def test_term_combined_with_vix_and_skew():
    """VIX 28 + term_ratio 1.08 + bearish -> all three stack."""
    result = compute_adaptive_params(
        bull_share=0.25, vix=28.0, base_config=BASE_CFG,
        adaptive_config=ADAPTIVE_CFG, term_ratio=1.08,
    )
    # VIX 25+ tier: delta_scale 0.70
    # Term moderate: x0.80
    # Combined delta: 0.70 * 0.80 = 0.56
    # Bearish max skew: put gets (1 + (-0.25)) = 0.75
    # put_delta_max = 0.15 * 0.56 * 0.75 = 0.063
    assert abs(result["put_delta_max"] - 0.063) < 0.001
    # call gets (1 - (-0.25)) = 1.25
    # call_delta_max = 0.15 * 0.56 * 1.25 = 0.105
    assert abs(result["call_delta_max"] - 0.105) < 0.001


def test_term_dte_floor_at_1():
    """DTE reduction never goes below 1."""
    result = compute_adaptive_params(
        bull_share=0.50, vix=28.0, base_config=BASE_CFG,
        adaptive_config=ADAPTIVE_CFG, term_ratio=1.15,
    )
    # VIX 25+ tier: DTE 3-15
    # Severe backwardation: -50% -> DTE 2-8 (3*0.50=1.5 rounds to 2)
    assert result["dte_min"] >= 1
    assert result["dte_max"] >= result["dte_min"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/mayongtao/projects/nodeble && .venv/bin/python -m pytest tests/test_adaptive.py -v -k "term" 2>&1 | tail -5`
Expected: FAIL (unexpected keyword argument 'term_ratio')

- [ ] **Step 3: Implement term structure scaling in adaptive.py**

Add default term structure tiers constant after `_FALLBACK_TIER` (line 12):

```python
_DEFAULT_TERM_TIERS = [
    {"max_ratio": 1.00, "delta_multiplier": 1.00, "dte_reduction": 0.00},
    {"max_ratio": 1.05, "delta_multiplier": 0.90, "dte_reduction": 0.15},
    {"max_ratio": 1.10, "delta_multiplier": 0.80, "dte_reduction": 0.30},
    {"max_ratio": 999,  "delta_multiplier": 0.65, "dte_reduction": 0.50},
]
```

Add helper function after `_get_vix_tier()`:

```python
def _get_term_structure_adjustment(term_ratio: float | None, tiers: list[dict]) -> tuple[float, float]:
    """Get delta multiplier and DTE reduction from term structure ratio.

    Returns (delta_multiplier, dte_reduction_fraction).
    """
    if term_ratio is None:
        logger.warning("Term ratio unavailable — no term structure adjustment")
        return 1.0, 0.0

    for tier in sorted(tiers, key=lambda t: t["max_ratio"]):
        if term_ratio <= tier["max_ratio"]:
            tier_name = "contango" if tier["max_ratio"] <= 1.0 else f"backwardation (ratio {term_ratio:.3f})"
            logger.info(
                f"Term structure: ratio={term_ratio:.3f} -> {tier_name} "
                f"(delta x{tier['delta_multiplier']}, DTE -{tier['dte_reduction']:.0%})"
            )
            return tier["delta_multiplier"], tier["dte_reduction"]

    return tiers[-1]["delta_multiplier"], tiers[-1]["dte_reduction"]
```

Update `compute_adaptive_params` signature and body. Add `term_ratio` parameter:

```python
def compute_adaptive_params(
    bull_share: float,
    vix: float | None,
    base_config: dict,
    adaptive_config: dict,
    term_ratio: float | None = None,
) -> dict:
```

After line 86 (`delta_scale = tier["delta_scale"]`), before line 87 (`dte_min = tier["dte_min"]`), insert term structure scaling:

```python
    # Step 1b: Term structure adjustment (stacks on VIX scaling)
    term_cfg = adaptive_config.get("term_structure", {})
    term_tiers = term_cfg.get("tiers", _DEFAULT_TERM_TIERS)
    term_multiplier, dte_reduction = _get_term_structure_adjustment(term_ratio, term_tiers)
    delta_scale *= term_multiplier

    dte_min = tier["dte_min"]
    dte_max = tier["dte_max"]

    # Apply DTE reduction from term structure
    if dte_reduction > 0:
        dte_min = max(1, round(dte_min * (1 - dte_reduction)))
        dte_max = max(dte_min, round(dte_max * (1 - dte_reduction)))

    dte_ideal = (dte_min + dte_max) // 2
```

Remove the old lines 87-89 that set `dte_min`, `dte_max`, `dte_ideal` since they're now in the block above.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/mayongtao/projects/nodeble && .venv/bin/python -m pytest tests/test_adaptive.py -v`
Expected: All tests pass (8 existing + 7 new = 15)

- [ ] **Step 5: Commit**

```bash
git add src/nodeble/strategy/adaptive.py tests/test_adaptive.py
git commit -m "feat: add VIX term structure scaling to adaptive layer"
```

---

### Task 3: Add dynamic profit targets to manager.py

**Files:**
- Modify: `src/nodeble/strategy/manager.py`
- Create: `tests/test_dynamic_targets.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_dynamic_targets.py
from nodeble.strategy.manager import _get_dynamic_profit_target


def test_vix_calm_target_40():
    """VIX 12 -> 40% profit target."""
    cfg = {"management": {"dynamic_profit_targets": [
        {"max_vix": 15, "profit_take_pct": 0.40},
        {"max_vix": 20, "profit_take_pct": 0.50},
        {"max_vix": 25, "profit_take_pct": 0.60},
        {"max_vix": 999, "profit_take_pct": 0.75},
    ]}}
    assert _get_dynamic_profit_target(cfg, 12.0) == 0.40


def test_vix_standard_target_50():
    """VIX 18 -> 50% profit target."""
    cfg = {"management": {"dynamic_profit_targets": [
        {"max_vix": 15, "profit_take_pct": 0.40},
        {"max_vix": 20, "profit_take_pct": 0.50},
        {"max_vix": 25, "profit_take_pct": 0.60},
        {"max_vix": 999, "profit_take_pct": 0.75},
    ]}}
    assert _get_dynamic_profit_target(cfg, 18.0) == 0.50


def test_vix_elevated_target_60():
    """VIX 22 -> 60% profit target."""
    cfg = {"management": {"dynamic_profit_targets": [
        {"max_vix": 15, "profit_take_pct": 0.40},
        {"max_vix": 20, "profit_take_pct": 0.50},
        {"max_vix": 25, "profit_take_pct": 0.60},
        {"max_vix": 999, "profit_take_pct": 0.75},
    ]}}
    assert _get_dynamic_profit_target(cfg, 22.0) == 0.60


def test_vix_high_target_75():
    """VIX 30 -> 75% profit target."""
    cfg = {"management": {"dynamic_profit_targets": [
        {"max_vix": 15, "profit_take_pct": 0.40},
        {"max_vix": 20, "profit_take_pct": 0.50},
        {"max_vix": 25, "profit_take_pct": 0.60},
        {"max_vix": 999, "profit_take_pct": 0.75},
    ]}}
    assert _get_dynamic_profit_target(cfg, 30.0) == 0.75


def test_vix_none_fallback_50():
    """VIX None -> 50% fallback."""
    cfg = {"management": {"dynamic_profit_targets": [
        {"max_vix": 15, "profit_take_pct": 0.40},
        {"max_vix": 20, "profit_take_pct": 0.50},
        {"max_vix": 25, "profit_take_pct": 0.60},
        {"max_vix": 999, "profit_take_pct": 0.75},
    ]}}
    assert _get_dynamic_profit_target(cfg, None) == 0.50


def test_no_dynamic_targets_falls_to_static():
    """No dynamic_profit_targets -> use static profit_take_pct."""
    cfg = {"management": {"profit_take_pct": 0.65}}
    assert _get_dynamic_profit_target(cfg, 18.0) == 0.65


def test_no_dynamic_targets_no_static_defaults_50():
    """No config at all -> default 0.50."""
    cfg = {"management": {}}
    assert _get_dynamic_profit_target(cfg, 18.0) == 0.50
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/mayongtao/projects/nodeble && .venv/bin/python -m pytest tests/test_dynamic_targets.py -v 2>&1 | tail -5`
Expected: FAIL (cannot import)

- [ ] **Step 3: Implement _get_dynamic_profit_target in manager.py**

Add after the `SpreadAction` class (around line 24):

```python
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
            logger.info(
                f"Dynamic profit target: VIX={vix:.1f}, "
                f"using {tier['profit_take_pct']:.0%} (tier <={tier['max_vix']})"
            )
            return tier["profit_take_pct"]

    return 0.50
```

- [ ] **Step 4: Update evaluate_positions to accept and use vix parameter**

Change the signature at line 141:

```python
def evaluate_positions(
    state: SpreadState,
    broker,
    strategy_cfg: dict,
    vix: float | None = None,
) -> list[SpreadAction]:
```

Replace line 151:
```python
    # OLD: profit_target_pct = mgmt.get("profit_take_pct", 0.50)
    # NEW:
    profit_target_pct = _get_dynamic_profit_target(strategy_cfg, vix)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /home/mayongtao/projects/nodeble && .venv/bin/python -m pytest tests/test_dynamic_targets.py -v`
Expected: 7 passed

- [ ] **Step 6: Run full test suite to check nothing breaks**

Run: `cd /home/mayongtao/projects/nodeble && .venv/bin/python -m pytest -v 2>&1 | tail -5`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add src/nodeble/strategy/manager.py tests/test_dynamic_targets.py
git commit -m "feat: add dynamic VIX-regime-aware profit targets"
```

---

### Task 4: Update signal_job.py to fetch VIX9D and compute term_ratio

**Files:**
- Modify: `src/nodeble/signals/signal_job.py`

- [ ] **Step 1: Add VIX9D fetch and term_ratio to run_signal_job**

In `signal_job.py`, add import at top:

```python
from nodeble.data.vix import get_vix, get_vix9d
```

In `run_signal_job()`, after the VIX fetch block (around line 130), add:

```python
    # Fetch VIX9D for term structure
    vix9d = get_vix9d()
    if vix9d is None:
        logger.warning("VIX9D unavailable — term structure gate disabled for this run")

    term_ratio = None
    term_structure = "unknown"
    if vix is not None and vix9d is not None and vix > 0:
        term_ratio = round(vix9d / vix, 4)
        if term_ratio <= 1.00:
            term_structure = "contango"
        elif term_ratio <= 1.05:
            term_structure = "mild_backwardation"
        elif term_ratio <= 1.10:
            term_structure = "moderate_backwardation"
        else:
            term_structure = "severe_backwardation"
        logger.info(f"Term structure: VIX9D={vix9d:.1f}, VIX={vix:.1f}, ratio={term_ratio:.3f} ({term_structure})")
```

Update the state dict to include the new fields:

```python
    state = {
        "version": 2,
        "generated_at": now.isoformat(),
        "vix": vix,
        "vix9d": vix9d,
        "term_ratio": term_ratio,
        "term_structure": term_structure,
        "vix_fallback": vix_fallback,
        "symbols": symbol_signals,
    }
```

- [ ] **Step 2: Update Telegram summary to include term structure**

In `__main__.py` `run_signal()`, update the Telegram message:

```python
    if notifier:
        vix_str = f"VIX {state['vix']:.1f}" if state["vix"] else "VIX unavailable"
        vix9d_str = f"VIX9D {state.get('vix9d', 0):.1f}" if state.get("vix9d") else ""
        term_str = ""
        if state.get("term_ratio"):
            term_str = f", {state['term_structure']} {state['term_ratio']:.2f}x"
        lines = [f"Signal Update ({vix_str}{', ' + vix9d_str if vix9d_str else ''}{term_str}):"]
```

- [ ] **Step 3: Verify signal state write includes new fields**

Run: `cd /home/mayongtao/projects/nodeble && .venv/bin/python -m pytest tests/test_signal_job.py -v`
Expected: All pass (existing tests still work with v2 state)

- [ ] **Step 4: Commit**

```bash
git add src/nodeble/signals/signal_job.py src/nodeble/__main__.py
git commit -m "feat: fetch VIX9D and compute term ratio in signal job"
```

---

### Task 5: Wire term_ratio through __main__.py and pass VIX to manage

**Files:**
- Modify: `src/nodeble/__main__.py`

- [ ] **Step 1: Update _apply_adaptive_params to read and pass term_ratio**

In `_apply_adaptive_params()`, after reading `signal_state`, extract term_ratio:

```python
    term_ratio = signal_state.get("term_ratio") if signal_state else None
```

Update both calls to `compute_adaptive_params()` to pass `term_ratio`:

```python
    # With signal state:
    adjusted = compute_adaptive_params(avg_bull_share, vix, sel, adaptive_cfg, term_ratio=term_ratio)

    # Fallback (no signal state):
    adjusted = compute_adaptive_params(0.50, None, sel, adaptive_cfg, term_ratio=None)
```

- [ ] **Step 2: Thread VIX through run_manage to evaluate_positions**

The `evaluate_positions()` call lives inside `run_manage()` (not directly in `main()`). Update `run_manage()` signature in `__main__.py` to accept and pass VIX:

```python
def run_manage(broker, notifier, state, state_path, risk_cfg, strategy_cfg, dry_run, vix=None):
```

Update the `evaluate_positions()` call inside `run_manage()`:

```python
    actions = evaluate_positions(
        state=state, broker=broker, strategy_cfg=strategy_cfg,
        vix=vix,
    )
```

In `main()`, fetch VIX before calling `run_manage()`:

```python
    elif args.mode == "manage":
        from nodeble.data.vix import get_vix
        manage_vix = get_vix()
        if manage_vix is None:
            logger.warning("VIX unavailable for dynamic profit targets, using defaults")
            if notifier:
                notifier.send("WARNING: VIX unavailable for profit targets, using 50% default.")
        results = run_manage(broker, notifier, state, state_path, risk_cfg, strategy_cfg, dry_run, vix=manage_vix)
```

- [ ] **Step 3: Run full test suite**

Run: `cd /home/mayongtao/projects/nodeble && .venv/bin/python -m pytest -v 2>&1 | tail -5`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add src/nodeble/__main__.py
git commit -m "feat: wire term_ratio to adaptive and VIX to manage"
```

---

### Task 6: Update config template

**Files:**
- Modify: `config/strategy.yaml.example`

- [ ] **Step 1: Add term_structure and dynamic_profit_targets to config**

In `config/strategy.yaml.example`, add `term_structure` inside the `adaptive` section (after `skew`):

```yaml
  term_structure:
    tiers:
      - { max_ratio: 1.00, delta_multiplier: 1.00, dte_reduction: 0.00 }
      - { max_ratio: 1.05, delta_multiplier: 0.90, dte_reduction: 0.15 }
      - { max_ratio: 1.10, delta_multiplier: 0.80, dte_reduction: 0.30 }
      - { max_ratio: 999,  delta_multiplier: 0.65, dte_reduction: 0.50 }
```

In the `management` section, replace the static `profit_take_pct` with dynamic targets:

```yaml
management:
  max_risk_per_trade: 2000
  # profit_take_pct: 0.50  # replaced by dynamic_profit_targets below
  stop_loss_pct: 2.0
  close_before_dte: 3

  dynamic_profit_targets:
    - { max_vix: 15,  profit_take_pct: 0.40 }
    - { max_vix: 20,  profit_take_pct: 0.50 }
    - { max_vix: 25,  profit_take_pct: 0.60 }
    - { max_vix: 999, profit_take_pct: 0.75 }
```

- [ ] **Step 2: Commit**

```bash
git add config/strategy.yaml.example
git commit -m "feat: add term structure and dynamic profit targets to config template"
```

---

### Task 7: Full integration test and push

**Files:**
- All

- [ ] **Step 1: Run full test suite**

Run: `cd /home/mayongtao/projects/nodeble && .venv/bin/python -m pytest -v`
Expected: All tests pass (~130 total)

- [ ] **Step 2: Commit docs**

```bash
git add docs/superpowers/
git commit -m "docs: add VIX term structure and dynamic targets spec and plan"
```

- [ ] **Step 3: Push**

```bash
git push origin main
```
