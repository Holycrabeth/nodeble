# Adaptive Iron Condor Strategy Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a two-layer adaptive system (directional indicators + VIX regime) that automatically computes optimal deltas and DTE for iron condor trades.

**Architecture:** A daily signal job runs 20 trend-following indicators (extracted from tiger-trading) and fetches VIX, writing results to a state file. Before each IC scan, the adaptive layer reads that file and computes skewed delta ranges and DTE, overwriting the strategy config before passing it to the existing factory.

**Tech Stack:** Python 3.12+, pandas, numpy, yfinance, pytest

**Spec:** `docs/superpowers/specs/2026-03-21-adaptive-strategy-design.md`

---

## File Structure

### New files to create

| File | Responsibility |
|------|---------------|
| `src/nodeble/signals/__init__.py` | Package init |
| `src/nodeble/signals/base.py` | BaseIndicator abstract class (extracted from tiger-trading) |
| `src/nodeble/signals/trend.py` | 5 trend indicators (extracted) |
| `src/nodeble/signals/momentum.py` | 5 momentum indicators (extracted) |
| `src/nodeble/signals/volatility.py` | 5 volatility indicators (extracted) |
| `src/nodeble/signals/volume.py` | 5 volume indicators (extracted) |
| `src/nodeble/signals/volume_filter.py` | Volume EMA smoothing utility (extracted) |
| `src/nodeble/signals/registry.py` | Builds the 20-indicator list from config (extracted) |
| `src/nodeble/signals/scorer.py` | VotingEngine + VoteResult (extracted) |
| `src/nodeble/signals/signal_job.py` | Entry point: fetch OHLCV, run indicators, fetch VIX, write state file |
| `src/nodeble/strategy/adaptive.py` | Pure function: signal + VIX + config → adjusted delta/DTE params |
| `config/signals.yaml.example` | Voting thresholds and indicator evolution config |
| `tests/test_adaptive.py` | Tests for adaptive parameter computation |
| `tests/test_scorer.py` | Tests for VotingEngine 4-gate system |
| `tests/test_signal_job.py` | Tests for signal state file read/write/staleness |

### Files to modify

| File | Change |
|------|--------|
| `src/nodeble/__main__.py` | Add `--mode signal`, read signal state, call adaptive layer before scan |
| `src/nodeble/strategy/factory.py` | Remove VIX scaling block (lines 107-112), it's now handled upstream |
| `config/strategy.yaml.example` | Add `adaptive` section, remove old `vix_scaling` |
| `deploy/deploy.sh` | Add signal cron job (9:30 AM ET) |

---

### Task 1: Extract BaseIndicator and volume_filter

**Files:**
- Create: `src/nodeble/signals/__init__.py`
- Create: `src/nodeble/signals/base.py`
- Create: `src/nodeble/signals/volume_filter.py`
- Test: `tests/test_scorer.py` (placeholder, used in Task 4)

- [ ] **Step 1: Create signals package with BaseIndicator**

Copy `reference/tiger-trading/indicators/base.py` to `src/nodeble/signals/base.py`. No import changes needed (only uses `abc` and `pandas`).

```python
# src/nodeble/signals/__init__.py
```

```python
# src/nodeble/signals/base.py
from abc import ABC, abstractmethod
import pandas as pd


class BaseIndicator(ABC):
    """Abstract indicator that casts a +1 / 0 / -1 vote."""

    name: str = ""
    category: str = ""  # "trend" | "momentum" | "volatility" | "volume"
    warmup_bars: int = 0

    @abstractmethod
    def compute(self, df: pd.DataFrame) -> int:
        """Compute indicator on OHLCV DataFrame.

        Returns: +1 (bullish), 0 (neutral), -1 (bearish)
        """
```

- [ ] **Step 2: Copy volume_filter.py**

Copy `reference/tiger-trading/indicators/volume_filter.py` to `src/nodeble/signals/volume_filter.py`. No import changes needed (only uses `pandas`).

```python
# src/nodeble/signals/volume_filter.py
import pandas as pd


def filtered_volume(volume: pd.Series, ema_span: int = 5) -> pd.Series:
    """EMA-smoothed volume to reduce single-day spike noise."""
    return volume.ewm(span=ema_span, adjust=False).mean()
```

- [ ] **Step 3: Verify imports work**

Run: `cd /home/mayongtao/projects/nodeble && .venv/bin/python -c "from nodeble.signals.base import BaseIndicator; from nodeble.signals.volume_filter import filtered_volume; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add src/nodeble/signals/__init__.py src/nodeble/signals/base.py src/nodeble/signals/volume_filter.py
git commit -m "feat: add signals package with BaseIndicator and volume_filter"
```

---

### Task 2: Extract 20 indicators (trend, momentum, volatility, volume)

**Files:**
- Create: `src/nodeble/signals/trend.py`
- Create: `src/nodeble/signals/momentum.py`
- Create: `src/nodeble/signals/volatility.py`
- Create: `src/nodeble/signals/volume.py`

- [ ] **Step 1: Copy trend.py and fix imports**

Copy `reference/tiger-trading/indicators/trend.py` to `src/nodeble/signals/trend.py`.

Fix import: `from indicators.base import BaseIndicator` → `from nodeble.signals.base import BaseIndicator`

- [ ] **Step 2: Copy momentum.py and fix imports**

Copy `reference/tiger-trading/indicators/momentum.py` to `src/nodeble/signals/momentum.py`.

Fix import: `from indicators.base import BaseIndicator` → `from nodeble.signals.base import BaseIndicator`

- [ ] **Step 3: Copy volatility.py and fix imports**

Copy `reference/tiger-trading/indicators/volatility.py` to `src/nodeble/signals/volatility.py`.

Fix import: `from indicators.base import BaseIndicator` → `from nodeble.signals.base import BaseIndicator`

- [ ] **Step 4: Copy volume.py and fix imports**

Copy `reference/tiger-trading/indicators/volume.py` to `src/nodeble/signals/volume.py`.

Fix imports:
- `from indicators.base import BaseIndicator` → `from nodeble.signals.base import BaseIndicator`
- `from indicators.volume_filter import filtered_volume` → `from nodeble.signals.volume_filter import filtered_volume`

- [ ] **Step 5: Verify all indicator imports work**

Run: `cd /home/mayongtao/projects/nodeble && .venv/bin/python -c "from nodeble.signals.trend import SMACross, EMACross, ADXTrend, Supertrend, AroonOscillator; from nodeble.signals.momentum import RSI, MACDHistogram, StochasticOscillator, CCI, WilliamsR; from nodeble.signals.volatility import BollingerBandPosition, KeltnerChannel, ATRTrend, DonchianChannel, BollingerBandWidth; from nodeble.signals.volume import OBVTrend, MFI, CMF, VWAPDistance, VolumeSMARatio; print('All 20 indicators imported OK')"`
Expected: `All 20 indicators imported OK`

- [ ] **Step 6: Commit**

```bash
git add src/nodeble/signals/trend.py src/nodeble/signals/momentum.py src/nodeble/signals/volatility.py src/nodeble/signals/volume.py
git commit -m "feat: extract 20 trend-following indicators from tiger-trading"
```

---

### Task 3: Extract registry.py (indicator builder)

**Files:**
- Create: `src/nodeble/signals/registry.py`
- Create: `config/signals.yaml.example`

- [ ] **Step 1: Copy registry.py and fix imports**

Copy `reference/tiger-trading/indicators/registry.py` to `src/nodeble/signals/registry.py`.

Fix all imports:
- `from indicators.trend import ...` → `from nodeble.signals.trend import ...`
- `from indicators.momentum import ...` → `from nodeble.signals.momentum import ...`
- `from indicators.volatility import ...` → `from nodeble.signals.volatility import ...`
- `from indicators.volume import ...` → `from nodeble.signals.volume import ...`

Fix config loading in `_load_indicator_evolution()`: change the default config path to use `nodeble.paths.get_config_dir()`:

```python
from nodeble.paths import get_config_dir

def _load_indicator_evolution(config_path: str = None) -> dict:
    if config_path is None:
        config_path = str(get_config_dir() / "signals.yaml")
    try:
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("indicator_evolution", {})
    except FileNotFoundError:
        return {}
```

- [ ] **Step 2: Create config/signals.yaml.example**

```yaml
# NODEBLE Signal Configuration — Voting thresholds and indicator evolution

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

- [ ] **Step 3: Verify registry builds 20 indicators**

Run: `cd /home/mayongtao/projects/nodeble && .venv/bin/python -c "from nodeble.signals.registry import get_all_indicators; inds = get_all_indicators(); print(f'{len(inds)} indicators built'); [print(f'  {i.name} ({i.category})') for i in inds]"`
Expected: `20 indicators built` followed by 20 lines

- [ ] **Step 4: Commit**

```bash
git add src/nodeble/signals/registry.py config/signals.yaml.example
git commit -m "feat: extract indicator registry with config-driven builder"
```

---

### Task 4: Extract VotingEngine (scorer.py)

**Files:**
- Create: `src/nodeble/signals/scorer.py`
- Create: `tests/test_scorer.py`

- [ ] **Step 1: Write failing tests for VotingEngine**

```python
# tests/test_scorer.py
import pandas as pd
from nodeble.signals.scorer import VotingEngine, VoteResult
from nodeble.signals.base import BaseIndicator


class StubIndicator(BaseIndicator):
    """Test stub that returns a fixed vote."""
    def __init__(self, name: str, category: str, vote: int):
        self.name = name
        self.category = category
        self.warmup_bars = 0
        self._vote = vote

    def compute(self, df: pd.DataFrame) -> int:
        return self._vote


def _make_indicators(votes: dict[str, list[int]]) -> list[StubIndicator]:
    """Build stub indicators from {category: [vote, vote, ...]}."""
    inds = []
    for cat, cat_votes in votes.items():
        for i, v in enumerate(cat_votes):
            inds.append(StubIndicator(f"{cat}_{i}", cat, v))
    return inds


def _empty_df():
    return pd.DataFrame({"open": [1], "high": [2], "low": [0.5], "close": [1.5], "volume": [100]})


def test_gate1_no_active_signal():
    """All neutral votes → HOLD (no_active_signal)."""
    engine = VotingEngine()
    inds = _make_indicators({
        "trend": [0, 0, 0, 0, 0],
        "momentum": [0, 0, 0, 0, 0],
        "volatility": [0, 0, 0, 0, 0],
        "volume": [0, 0, 0, 0, 0],
    })
    result = engine.score("SPY", _empty_df(), inds)
    assert result.decision == "HOLD"
    assert result.reason == "no_active_signal"


def test_gate2_below_quorum():
    """Only 4/20 active (20%) < 35% quorum → HOLD."""
    engine = VotingEngine()
    inds = _make_indicators({
        "trend": [1, 0, 0, 0, 0],
        "momentum": [1, 0, 0, 0, 0],
        "volatility": [1, 0, 0, 0, 0],
        "volume": [1, 0, 0, 0, 0],
    })
    result = engine.score("SPY", _empty_df(), inds)
    assert result.decision == "HOLD"
    assert result.reason == "below_quorum"


def test_gate3_insufficient_categories():
    """Active in only 2 categories < 3 required → HOLD."""
    engine = VotingEngine()
    inds = _make_indicators({
        "trend": [1, 1, 1, 1, 1],
        "momentum": [1, 1, 1, 0, 0],
        "volatility": [0, 0, 0, 0, 0],
        "volume": [0, 0, 0, 0, 0],
    })
    result = engine.score("SPY", _empty_df(), inds)
    assert result.decision == "HOLD"
    assert result.reason == "insufficient_category_diversity"


def test_gate4_deadband():
    """bull_share ~0.50 within ±0.06 deadband → HOLD."""
    engine = VotingEngine()
    # 10 bull, 10 bear → bull_share = 0.50 → in deadband
    inds = _make_indicators({
        "trend": [1, 1, -1, -1, 1],
        "momentum": [-1, 1, -1, 1, -1],
        "volatility": [1, -1, 1, -1, 1],
        "volume": [-1, -1, 1, 1, -1],
    })
    result = engine.score("SPY", _empty_df(), inds)
    assert result.decision == "HOLD"
    assert result.reason == "in_deadband"


def test_strong_buy():
    """bull_share >= 0.70 → STRONG_BUY."""
    engine = VotingEngine()
    # 14 bull, 6 bear → bull_share = 0.70
    inds = _make_indicators({
        "trend": [1, 1, 1, 1, 1],
        "momentum": [1, 1, 1, 1, -1],
        "volatility": [1, 1, 1, -1, -1],
        "volume": [1, 1, -1, -1, -1],
    })
    result = engine.score("SPY", _empty_df(), inds)
    assert result.decision == "STRONG_BUY"
    assert result.bull_share >= 0.70


def test_sell_signal():
    """bear_share >= 0.58 → SELL."""
    engine = VotingEngine()
    # 8 bull, 12 bear → bear_share = 0.60
    inds = _make_indicators({
        "trend": [-1, -1, -1, 1, 1],
        "momentum": [-1, -1, -1, 1, 1],
        "volatility": [-1, -1, -1, 1, 1],
        "volume": [-1, -1, -1, 1, 1],
    })
    result = engine.score("SPY", _empty_df(), inds)
    assert result.decision in ("SELL", "STRONG_SELL")
    assert result.bear_share >= 0.58


def test_vote_result_fields():
    """VoteResult has all expected fields."""
    engine = VotingEngine()
    inds = _make_indicators({
        "trend": [1, 1, 1, 1, 1],
        "momentum": [1, 1, 1, 1, 1],
        "volatility": [1, 1, 1, 1, 1],
        "volume": [1, 1, 1, 1, 1],
    })
    result = engine.score("SPY", _empty_df(), inds)
    assert result.symbol == "SPY"
    assert isinstance(result.bull_share, float)
    assert isinstance(result.confidence, float)
    assert isinstance(result.votes, dict)
    assert len(result.votes) == 20
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/mayongtao/projects/nodeble && .venv/bin/python -m pytest tests/test_scorer.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Copy scorer.py and fix imports**

Copy `reference/tiger-trading/engine/scorer.py` to `src/nodeble/signals/scorer.py`.

Fix import: `from indicators.base import BaseIndicator` → `from nodeble.signals.base import BaseIndicator`

Fix config loading in `VotingEngine.__init__()` and `load_voting_config()`: change default config path to use `nodeble.paths.get_config_dir()`:

```python
from nodeble.paths import get_config_dir

def load_voting_config(path: str = None) -> dict:
    if path is None:
        path = str(get_config_dir() / "signals.yaml")
    try:
        with open(path, "r") as f:
            cfg = yaml.safe_load(f) or {}
        return cfg.get("voting", {})
    except FileNotFoundError:
        return {}
```

Update `VotingEngine.__init__` to accept a dict directly (not just a file path):

```python
class VotingEngine:
    def __init__(self, config: dict = None):
        if config is None:
            config = load_voting_config()
        self.implemented = config.get("implemented_indicators", 20)
        self.min_active_ratio = config.get("min_active_ratio", 0.35)
        self.min_active_categories = config.get("min_active_categories", 3)
        self.deadband = config.get("deadband", 0.06)
        self.buy_threshold = config.get("buy_threshold", 0.58)
        self.strong_buy_threshold = config.get("strong_buy_threshold", 0.70)
        self.sell_threshold = config.get("sell_threshold", 0.58)
        self.strong_sell_threshold = config.get("strong_sell_threshold", 0.70)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/mayongtao/projects/nodeble && .venv/bin/python -m pytest tests/test_scorer.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/nodeble/signals/scorer.py tests/test_scorer.py
git commit -m "feat: extract VotingEngine with 4-gate quorum system"
```

---

### Task 5: Build adaptive.py (pure function)

**Files:**
- Create: `src/nodeble/strategy/adaptive.py`
- Create: `tests/test_adaptive.py`

- [ ] **Step 1: Write failing tests for adaptive parameter computation**

```python
# tests/test_adaptive.py
from nodeble.strategy.adaptive import compute_adaptive_params

# Default adaptive config matching strategy.yaml.example
ADAPTIVE_CFG = {
    "vix_tiers": [
        {"max_vix": 15, "delta_scale": 1.50, "dte_min": 15, "dte_max": 30},
        {"max_vix": 20, "delta_scale": 1.00, "dte_min": 12, "dte_max": 25},
        {"max_vix": 25, "delta_scale": 0.85, "dte_min": 7, "dte_max": 20},
        {"max_vix": 999, "delta_scale": 0.70, "dte_min": 3, "dte_max": 15},
    ],
    "skew": {
        "neutral_zone": [0.45, 0.55],
        "max_skew_ratio": 0.25,
    },
}

# Base selection config (from strategy.yaml)
BASE_CFG = {
    "put_delta_min": 0.08,
    "put_delta_max": 0.15,
    "call_delta_min": 0.08,
    "call_delta_max": 0.15,
    "dte_min": 30,
    "dte_max": 45,
    "dte_ideal": 35,
}


def test_vix_calm_scales_up():
    """VIX <= 15 → delta_scale 1.50, DTE 15-30."""
    result = compute_adaptive_params(
        bull_share=0.50, vix=12.0, base_config=BASE_CFG, adaptive_config=ADAPTIVE_CFG,
    )
    # Base put_delta_max 0.15 * 1.50 = 0.225
    assert abs(result["put_delta_max"] - 0.225) < 0.001
    assert abs(result["call_delta_max"] - 0.225) < 0.001
    assert result["dte_min"] == 15
    assert result["dte_max"] == 30
    assert result["dte_ideal"] == 22  # midpoint of 15-30


def test_vix_high_scales_down():
    """VIX 25+ → delta_scale 0.70, DTE 3-15."""
    result = compute_adaptive_params(
        bull_share=0.50, vix=30.0, base_config=BASE_CFG, adaptive_config=ADAPTIVE_CFG,
    )
    # Base put_delta_max 0.15 * 0.70 = 0.105
    assert abs(result["put_delta_max"] - 0.105) < 0.001
    assert result["dte_min"] == 3
    assert result["dte_max"] == 15
    assert result["dte_ideal"] == 9  # midpoint of 3-15


def test_vix_unavailable_falls_to_middle():
    """VIX None → use 15-20 tier (delta_scale 1.00)."""
    result = compute_adaptive_params(
        bull_share=0.50, vix=None, base_config=BASE_CFG, adaptive_config=ADAPTIVE_CFG,
    )
    # delta_scale 1.00 → unchanged
    assert abs(result["put_delta_max"] - 0.15) < 0.001
    assert result["dte_min"] == 12
    assert result["dte_max"] == 25


def test_neutral_symmetric():
    """bull_share 0.50 (neutral zone) → symmetric deltas."""
    result = compute_adaptive_params(
        bull_share=0.50, vix=18.0, base_config=BASE_CFG, adaptive_config=ADAPTIVE_CFG,
    )
    assert result["put_delta_max"] == result["call_delta_max"]
    assert result["put_delta_min"] == result["call_delta_min"]


def test_bearish_skew():
    """bull_share 0.35 (bearish) → put delta lower, call delta higher."""
    result = compute_adaptive_params(
        bull_share=0.35, vix=18.0, base_config=BASE_CFG, adaptive_config=ADAPTIVE_CFG,
    )
    # Bearish: put side dangerous → lower delta (farther OTM)
    assert result["put_delta_max"] < result["call_delta_max"]
    assert result["put_delta_min"] < result["call_delta_min"]


def test_bullish_skew():
    """bull_share 0.70 (bullish) → call delta lower, put delta higher."""
    result = compute_adaptive_params(
        bull_share=0.70, vix=18.0, base_config=BASE_CFG, adaptive_config=ADAPTIVE_CFG,
    )
    # Bullish: call side dangerous → lower delta (farther OTM)
    assert result["call_delta_max"] < result["put_delta_max"]
    assert result["call_delta_min"] < result["put_delta_min"]


def test_max_skew_at_extreme():
    """bull_share 0.25 (strongly bearish, <= 0.30 clamp) → maximum skew ratio applied."""
    result = compute_adaptive_params(
        bull_share=0.25, vix=18.0, base_config=BASE_CFG, adaptive_config=ADAPTIVE_CFG,
    )
    # bull_share <= 0.30 → clamped to max skew (-0.25)
    # Base 0.15 * 1.00 (VIX 15-20) = 0.15
    # put_delta_max = 0.15 * (1 + (-0.25)) = 0.15 * 0.75 = 0.1125
    # call_delta_max = 0.15 * (1 - (-0.25)) = 0.15 * 1.25 = 0.1875
    assert abs(result["put_delta_max"] - 0.1125) < 0.001
    assert abs(result["call_delta_max"] - 0.1875) < 0.001


def test_combined_vix_and_skew():
    """VIX calm + strongly bearish → scaled up AND max skewed."""
    result = compute_adaptive_params(
        bull_share=0.25, vix=12.0, base_config=BASE_CFG, adaptive_config=ADAPTIVE_CFG,
    )
    # VIX <=15: delta_scale 1.50 → base 0.15 * 1.50 = 0.225
    # bull_share 0.25 <= 0.30 → clamped to max skew (-0.25)
    # put_delta_max = 0.225 * 0.75 = 0.16875
    # call_delta_max = 0.225 * 1.25 = 0.28125
    assert abs(result["put_delta_max"] - 0.16875) < 0.001
    assert abs(result["call_delta_max"] - 0.28125) < 0.001
    assert result["dte_min"] == 15
    assert result["dte_max"] == 30
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/mayongtao/projects/nodeble && .venv/bin/python -m pytest tests/test_adaptive.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement adaptive.py**

```python
# src/nodeble/strategy/adaptive.py
"""Adaptive parameter computation for iron condor strategy.

Pure function: signal state + VIX + base config → adjusted delta/DTE params.
No side effects, no I/O, no broker calls.
"""
import logging

logger = logging.getLogger(__name__)

# Fallback tier when VIX is unavailable (15-20 range = standard posture)
_FALLBACK_TIER = {"max_vix": 20, "delta_scale": 1.00, "dte_min": 12, "dte_max": 25}


def _get_vix_tier(vix: float | None, tiers: list[dict]) -> dict:
    """Match VIX to the first tier where vix <= max_vix."""
    if vix is None:
        logger.warning("VIX unavailable — using fallback tier (15-20)")
        return _FALLBACK_TIER

    for tier in sorted(tiers, key=lambda t: t["max_vix"]):
        if vix <= tier["max_vix"]:
            return tier

    # Should not reach here if tiers include a catch-all (max_vix: 999)
    return tiers[-1]


def _compute_skew(bull_share: float, neutral_zone: list, max_skew_ratio: float) -> float:
    """Compute skew adjustment factor from bull_share.

    Returns a value in [-max_skew_ratio, +max_skew_ratio].
    Positive = bullish (tighten call, loosen put).
    Negative = bearish (tighten put, loosen call).
    Zero = neutral (no skew).

    Skew clamps to max at bull_share <= 0.30 or >= 0.70 (strongly directional).
    Between neutral zone and clamp point, scales linearly.
    """
    low, high = neutral_zone
    # Clamp points where max skew is reached
    clamp_low = 0.30
    clamp_high = 0.70

    if low <= bull_share <= high:
        return 0.0

    if bull_share < low:
        # Bearish: scale linearly from 0 at low to -max_skew_ratio at clamp_low
        if bull_share <= clamp_low:
            return -max_skew_ratio
        distance = (low - bull_share) / (low - clamp_low) if low > clamp_low else 1.0
        return -min(distance, 1.0) * max_skew_ratio
    else:
        # Bullish: scale linearly from 0 at high to +max_skew_ratio at clamp_high
        if bull_share >= clamp_high:
            return max_skew_ratio
        distance = (bull_share - high) / (clamp_high - high) if clamp_high > high else 1.0
        return min(distance, 1.0) * max_skew_ratio


def compute_adaptive_params(
    bull_share: float,
    vix: float | None,
    base_config: dict,
    adaptive_config: dict,
) -> dict:
    """Compute VIX-scaled, direction-skewed parameters.

    Args:
        bull_share: Directional signal (0.0 = strongly bearish, 1.0 = strongly bullish)
        vix: Current VIX level (None if unavailable)
        base_config: User's strategy.yaml selection section
        adaptive_config: User's strategy.yaml adaptive section

    Returns:
        Dict with put/call delta ranges and DTE range.
    """
    tiers = adaptive_config.get("vix_tiers", [_FALLBACK_TIER])
    skew_cfg = adaptive_config.get("skew", {})
    neutral_zone = skew_cfg.get("neutral_zone", [0.45, 0.55])
    max_skew_ratio = skew_cfg.get("max_skew_ratio", 0.25)

    # Step 1: VIX tier → delta scale + DTE range
    tier = _get_vix_tier(vix, tiers)
    delta_scale = tier["delta_scale"]
    dte_min = tier["dte_min"]
    dte_max = tier["dte_max"]
    dte_ideal = (dte_min + dte_max) // 2

    # Step 2: Directional skew
    skew = _compute_skew(bull_share, neutral_zone, max_skew_ratio)

    # Step 3: Apply to both min and max independently
    # Negative skew (bearish): put gets tighter (lower delta), call gets looser (higher delta)
    # Put adjustment: (1 + skew) where skew is negative → shrinks put delta
    # Call adjustment: (1 - skew) where skew is negative → grows call delta
    put_delta_min = base_config.get("put_delta_min", 0.08) * delta_scale * (1 + skew)
    put_delta_max = base_config.get("put_delta_max", 0.15) * delta_scale * (1 + skew)
    call_delta_min = base_config.get("call_delta_min", 0.08) * delta_scale * (1 - skew)
    call_delta_max = base_config.get("call_delta_max", 0.15) * delta_scale * (1 - skew)

    return {
        "put_delta_min": put_delta_min,
        "put_delta_max": put_delta_max,
        "call_delta_min": call_delta_min,
        "call_delta_max": call_delta_max,
        "dte_min": dte_min,
        "dte_max": dte_max,
        "dte_ideal": dte_ideal,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/mayongtao/projects/nodeble && .venv/bin/python -m pytest tests/test_adaptive.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add src/nodeble/strategy/adaptive.py tests/test_adaptive.py
git commit -m "feat: add adaptive parameter computation (VIX scaling + directional skew)"
```

---

### Task 6: Build signal_job.py (signal generation entry point)

**Files:**
- Create: `src/nodeble/signals/signal_job.py`
- Create: `tests/test_signal_job.py`

- [ ] **Step 1: Write failing tests for signal state read/write**

```python
# tests/test_signal_job.py
import json
import os
import tempfile
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import patch

from nodeble.signals.signal_job import (
    write_signal_state,
    read_signal_state,
    SIGNAL_STATE_FILE,
)


def test_write_and_read_signal_state(tmp_path):
    """Write signal state → read it back → matches."""
    state_path = str(tmp_path / "signal_state.json")
    state = {
        "version": 1,
        "generated_at": "2026-03-21T09:30:00-04:00",
        "vix": 18.5,
        "vix_tier": "15-20",
        "vix_fallback": False,
        "symbols": {
            "SPY": {
                "bull_share": 0.35,
                "decision": "SELL",
                "confidence": 0.30,
            }
        },
    }
    write_signal_state(state, state_path)

    loaded = read_signal_state(state_path)
    assert loaded is not None
    assert loaded["vix"] == 18.5
    assert loaded["symbols"]["SPY"]["bull_share"] == 0.35


def test_read_missing_file_returns_none(tmp_path):
    """Missing file → returns None."""
    result = read_signal_state(str(tmp_path / "nonexistent.json"))
    assert result is None


def test_read_stale_file_returns_none(tmp_path):
    """File older than 24h → returns None."""
    state_path = str(tmp_path / "signal_state.json")
    old_time = (datetime.now(ZoneInfo("America/New_York")) - timedelta(hours=25)).isoformat()
    state = {
        "version": 1,
        "generated_at": old_time,
        "vix": 18.5,
        "symbols": {},
    }
    write_signal_state(state, state_path)

    result = read_signal_state(state_path)
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/mayongtao/projects/nodeble && .venv/bin/python -m pytest tests/test_signal_job.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement signal_job.py**

```python
# src/nodeble/signals/signal_job.py
"""Signal generation job: fetch OHLCV, run 20 indicators, fetch VIX, write state."""
import json
import logging
import os
import tempfile
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from nodeble.paths import get_data_dir, get_config_dir
from nodeble.data.fetcher import DataFetcher
from nodeble.data.vix import get_vix
from nodeble.signals.registry import get_all_indicators, get_max_warmup
from nodeble.signals.scorer import VotingEngine, load_voting_config

logger = logging.getLogger(__name__)

NY = ZoneInfo("America/New_York")
SIGNAL_STATE_FILE = "signal_state.json"
STALENESS_HOURS = 24


def write_signal_state(state: dict, path: str = None):
    """Atomic write signal state to JSON file."""
    if path is None:
        data_dir = get_data_dir() / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        path = str(data_dir / SIGNAL_STATE_FILE)

    dir_name = os.path.dirname(path)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state, f, indent=2, default=str)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def read_signal_state(path: str = None) -> dict | None:
    """Read signal state. Returns None if missing or stale (>24h)."""
    if path is None:
        path = str(get_data_dir() / "data" / SIGNAL_STATE_FILE)

    try:
        with open(path, "r") as f:
            state = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning(f"Signal state file missing or corrupt: {path}")
        return None

    # Check staleness
    generated_at = state.get("generated_at")
    if generated_at:
        try:
            gen_time = datetime.fromisoformat(generated_at)
            now = datetime.now(NY)
            if (now - gen_time) > timedelta(hours=STALENESS_HOURS):
                logger.warning(
                    f"Signal state is stale (generated {generated_at}, "
                    f">{STALENESS_HOURS}h ago)"
                )
                return None
        except (ValueError, TypeError):
            logger.warning(f"Invalid generated_at in signal state: {generated_at}")
            return None

    return state


def _determine_vix_tier(vix: float | None, adaptive_cfg: dict) -> str:
    """Return human-readable VIX tier string."""
    if vix is None:
        return "unavailable"
    tiers = adaptive_cfg.get("vix_tiers", [])
    prev_max = 0
    for tier in sorted(tiers, key=lambda t: t["max_vix"]):
        if vix <= tier["max_vix"]:
            return f"{prev_max}-{tier['max_vix']}" if tier["max_vix"] < 999 else f"{prev_max}+"
        prev_max = tier["max_vix"]
    return "unknown"


def run_signal_job(watchlist: list[str], strategy_cfg: dict) -> dict:
    """Run the full signal generation pipeline.

    1. Fetch 252-day OHLCV per symbol
    2. Run 20 indicators → VotingEngine → bull_share per symbol
    3. Fetch VIX
    4. Write signal_state.json

    Returns the signal state dict.
    """
    signals_cfg_path = str(get_config_dir() / "signals.yaml")
    indicators = get_all_indicators(signals_cfg_path)
    voting_config = load_voting_config(signals_cfg_path)
    engine = VotingEngine(config=voting_config)

    warmup = get_max_warmup()
    lookback_days = max(warmup + 50, 300)  # Ensure enough bars

    fetcher = DataFetcher()  # yfinance only (no broker needed for signals)
    today = date.today()
    start = today - timedelta(days=int(lookback_days * 1.5))  # Account for weekends/holidays

    # Fetch OHLCV
    bars = fetcher.get_daily_bars_batch(watchlist, start, today)

    # Score each symbol
    symbol_signals = {}
    for symbol in watchlist:
        df = bars.get(symbol)
        if df is None or df.empty:
            logger.warning(f"No OHLCV data for {symbol} — skipping signal")
            continue

        result = engine.score(symbol, df, indicators)
        symbol_signals[symbol] = {
            "bull_share": result.bull_share,
            "decision": result.decision,
            "confidence": result.confidence,
            "bull_count": result.bull_count,
            "bear_count": result.bear_count,
            "active_count": result.active_count,
            "active_ratio": result.active_ratio,
            "votes": result.votes,
        }

    # Fetch VIX
    vix = get_vix()
    vix_fallback = vix is None
    if vix_fallback:
        logger.warning("VIX unavailable — signal state will indicate fallback")

    adaptive_cfg = strategy_cfg.get("adaptive", {})
    vix_tier = _determine_vix_tier(vix, adaptive_cfg)

    # Build state
    now = datetime.now(NY)
    state = {
        "version": 1,
        "generated_at": now.isoformat(),
        "vix": vix,
        "vix_tier": vix_tier,
        "vix_fallback": vix_fallback,
        "symbols": symbol_signals,
    }

    write_signal_state(state)
    logger.info(f"Signal state written: {len(symbol_signals)} symbols, VIX={vix}")
    return state
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/mayongtao/projects/nodeble && .venv/bin/python -m pytest tests/test_signal_job.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/nodeble/signals/signal_job.py tests/test_signal_job.py
git commit -m "feat: add signal generation job with state file read/write"
```

---

### Task 7: Integrate adaptive layer into __main__.py

**Files:**
- Modify: `src/nodeble/__main__.py`
- Modify: `src/nodeble/strategy/factory.py:107-112` (remove old VIX scaling)
- Modify: `config/strategy.yaml.example`

- [ ] **Step 1: Add `adaptive` section to config/strategy.yaml.example**

Add to the end of `config/strategy.yaml.example` (before the health_check_url comment):

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

- [ ] **Step 2: Remove old VIX scaling block from factory.py**

In `src/nodeble/strategy/factory.py`, remove lines 107-112 (the `vix_scaling` block inside `scan_for_condors`):

```python
    # DELETE these lines:
    # VIX scaling — apply tier overrides to selection config
    from nodeble.data.vix import get_vix, apply_vix_overrides
    vix_scaling = strategy_cfg.get("vix_scaling", {})
    if vix_scaling.get("enabled", False):
        vix = get_vix()
        sel = apply_vix_overrides(sel, vix, vix_scaling)
```

- [ ] **Step 3: Add `--mode signal` to __main__.py**

Add imports at top of `__main__.py`:

```python
from nodeble.signals.signal_job import run_signal_job, read_signal_state
from nodeble.strategy.adaptive import compute_adaptive_params
```

Update `parser.add_argument("--mode")` to include `"signal"`:

```python
parser.add_argument("--mode", choices=["scan", "manage", "signal"], help="Run mode")
```

Add `run_signal` function:

```python
def run_signal(notifier, strategy_cfg):
    """Run signal generation job and send Telegram summary."""
    watchlist = strategy_cfg.get("watchlist", [])
    if not watchlist:
        logger.warning("Empty watchlist — nothing to signal")
        return

    state = run_signal_job(watchlist, strategy_cfg)

    # Telegram summary
    if notifier:
        vix_str = f"VIX {state['vix']:.1f}" if state["vix"] else "VIX unavailable"
        lines = [f"Signal Update ({vix_str}):"]
        for sym, sig in state["symbols"].items():
            direction = "bearish" if sig["bull_share"] < 0.45 else "bullish" if sig["bull_share"] > 0.55 else "neutral"
            lines.append(f"{sym}: {direction} (bull {sig['bull_share']:.0%}, {sig['active_count']}/20)")
        notifier.send("\n".join(lines))
```

In `main()`, add signal mode handling and adaptive integration for scan mode:

```python
    if args.mode == "signal":
        notifier = load_notifier()
        run_signal(notifier, strategy_cfg)
        _ping_health_check(strategy_cfg)
        return
```

For scan mode, add adaptive layer before `run_scan()`:

```python
    # Adaptive parameter adjustment (before scan)
    if args.mode == "scan":
        signal_state = read_signal_state()
        if signal_state is None:
            logger.warning("Signal data unavailable, using fallback defaults")
            if notifier:
                notifier.send("WARNING: Signal data unavailable, IC scan using fallback defaults. Check signal job.")
```

Then for each symbol, apply adaptive params by overwriting the selection config:

```python
        # Apply adaptive params per-symbol (use first symbol's signal as global for now,
        # since factory iterates the watchlist internally)
        adaptive_cfg = strategy_cfg.get("adaptive", {})
        if signal_state and adaptive_cfg:
            # Use the average bull_share across all symbols for global adjustment
            symbols_data = signal_state.get("symbols", {})
            if symbols_data:
                avg_bull_share = sum(s["bull_share"] for s in symbols_data.values()) / len(symbols_data)
            else:
                avg_bull_share = 0.50

            vix = signal_state.get("vix")
            sel = strategy_cfg.get("selection", {})
            adjusted = compute_adaptive_params(avg_bull_share, vix, sel, adaptive_cfg)

            # Overwrite selection with adjusted values
            strategy_cfg["selection"]["put_delta_min"] = adjusted["put_delta_min"]
            strategy_cfg["selection"]["put_delta_max"] = adjusted["put_delta_max"]
            strategy_cfg["selection"]["call_delta_min"] = adjusted["call_delta_min"]
            strategy_cfg["selection"]["call_delta_max"] = adjusted["call_delta_max"]
            strategy_cfg["selection"]["dte_min"] = adjusted["dte_min"]
            strategy_cfg["selection"]["dte_max"] = adjusted["dte_max"]
            strategy_cfg["selection"]["dte_ideal"] = adjusted["dte_ideal"]

            logger.info(
                f"Adaptive params applied: VIX={vix}, bull_share={avg_bull_share:.2f}, "
                f"put_delta=[{adjusted['put_delta_min']:.3f}-{adjusted['put_delta_max']:.3f}], "
                f"call_delta=[{adjusted['call_delta_min']:.3f}-{adjusted['call_delta_max']:.3f}], "
                f"DTE=[{adjusted['dte_min']}-{adjusted['dte_max']}]"
            )
        elif adaptive_cfg:
            # No signal state — use fallback (VIX 15-20 tier, symmetric)
            sel = strategy_cfg.get("selection", {})
            adjusted = compute_adaptive_params(0.50, None, sel, adaptive_cfg)
            strategy_cfg["selection"].update(adjusted)
            logger.info("Adaptive params applied with fallback defaults (no signal data)")
```

- [ ] **Step 4: Run existing tests to verify nothing breaks**

Run: `cd /home/mayongtao/projects/nodeble && .venv/bin/python -m pytest -v`
Expected: All existing tests + new tests pass

- [ ] **Step 5: Commit**

```bash
git add src/nodeble/__main__.py src/nodeble/strategy/factory.py config/strategy.yaml.example
git commit -m "feat: integrate adaptive layer into CLI and remove old VIX scaling"
```

---

### Task 8: Update deploy.sh with signal cron job

**Files:**
- Modify: `deploy/deploy.sh`

- [ ] **Step 1: Add signal cron job to deploy.sh**

In `deploy/deploy.sh`, update the cron section (around line 157) to add the signal job before the scan job:

```bash
cat >> /tmp/crontab_clean << CRON
# NODEBLE signal — weekdays 9:30 AM ET
30 9 * * 1-5 cd $NODEBLE_DIR && .venv/bin/python -m nodeble --mode signal >> $NODEBLE_DATA/logs/cron.log 2>&1
# NODEBLE scan — weekdays 10:00 AM ET
0 10 * * 1-5 cd $NODEBLE_DIR && .venv/bin/python -m nodeble --mode scan >> $NODEBLE_DATA/logs/cron.log 2>&1
# NODEBLE manage — weekdays 10:30 AM and 3:00 PM ET
30 10 * * 1-5 cd $NODEBLE_DIR && .venv/bin/python -m nodeble --mode manage >> $NODEBLE_DATA/logs/cron.log 2>&1
0 15 * * 1-5 cd $NODEBLE_DIR && .venv/bin/python -m nodeble --mode manage --force >> $NODEBLE_DATA/logs/cron.log 2>&1
CRON
```

Also add `signals.yaml` to the config copy step. After the strategy template copy (around line 101), add:

```bash
cp "$NODEBLE_DIR/config/signals.yaml.example" "$NODEBLE_DATA/config/signals.yaml"
```

- [ ] **Step 2: Commit**

```bash
git add deploy/deploy.sh
git commit -m "feat: add signal cron job and signals.yaml to deploy script"
```

---

### Task 9: Full integration test

**Files:**
- Existing test files

- [ ] **Step 1: Run full test suite**

Run: `cd /home/mayongtao/projects/nodeble && .venv/bin/python -m pytest -v`
Expected: All tests pass (existing 96 + new ~18 = ~114 total)

- [ ] **Step 2: Test CLI signal mode end-to-end (dry run)**

Run: `cd /home/mayongtao/projects/nodeble && .venv/bin/python -m nodeble --mode signal --dry-run 2>&1 | head -30`
Expected: Signal job runs, fetches OHLCV from yfinance, writes signal_state.json (or fails gracefully if no config)

- [ ] **Step 3: Verify signal state file was written**

Run: `cat ~/.nodeble/data/signal_state.json 2>/dev/null || echo "File not written (expected if no config)"`

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "fix: integration test fixes"
```

---

### Task 10: Push to GitHub

- [ ] **Step 1: Run full test suite one final time**

Run: `cd /home/mayongtao/projects/nodeble && .venv/bin/python -m pytest -v`
Expected: All tests pass

- [ ] **Step 2: Push**

```bash
cd /home/mayongtao/projects/nodeble && git push origin master
```
