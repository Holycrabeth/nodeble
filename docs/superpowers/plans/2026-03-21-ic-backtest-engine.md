# IC Backtest Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a backtest engine that simulates 5 years of iron condor trades, supports parameter sweep, and runs feature importance analysis on the 20 indicators.

**Architecture:** The engine lives at `src/nodeble/backtest/` and reuses existing indicators, VotingEngine, and adaptive layer. Data is fetched from yfinance and cached to Parquet. IC positions are priced using Black-Scholes. Results feed into a Random Forest for indicator importance analysis.

**Tech Stack:** Python 3.12+, scipy (BS pricing), scikit-learn (feature importance), pandas, numpy, yfinance

**Spec:** `docs/superpowers/specs/2026-03-21-ic-backtest-engine-design.md`

---

## File Structure

### New

| File | Responsibility |
|------|---------------|
| `src/nodeble/backtest/__init__.py` | Package init |
| `src/nodeble/backtest/data.py` | Fetch + cache OHLCV, VIX, VIX9D to Parquet |
| `src/nodeble/backtest/pricing.py` | Black-Scholes pricing, delta, strike finder |
| `src/nodeble/backtest/simulator.py` | Day-by-day IC simulation: entry, daily eval, exit |
| `src/nodeble/backtest/sweep.py` | Parameter sweep grid search |
| `src/nodeble/backtest/analysis.py` | Random Forest feature importance + report |
| `src/nodeble/backtest/runner.py` | Orchestrator: data → simulate → sweep → analyze |
| `tests/test_pricing.py` | BS formula correctness |
| `tests/test_simulator.py` | Simulator entry/exit/P&L logic |

### Modified

| File | Change |
|------|--------|
| `src/nodeble/__main__.py` | Add `--mode backtest` with flags |
| `pyproject.toml` | Add `scikit-learn`, `scipy` deps |

---

### Task 1: Add dependencies and create backtest package

**Files:**
- Modify: `pyproject.toml`
- Create: `src/nodeble/backtest/__init__.py`

- [ ] **Step 1: Add scipy and scikit-learn to pyproject.toml**

Add to the `dependencies` list in `pyproject.toml`:

```toml
dependencies = [
    "tigeropen",
    "pyyaml",
    "yfinance",
    "pandas",
    "numpy",
    "pyarrow",
    "pandas-market-calendars",
    "requests",
    "python-telegram-bot",
    "scipy",
    "scikit-learn",
]
```

- [ ] **Step 2: Create backtest package**

```python
# src/nodeble/backtest/__init__.py
```

- [ ] **Step 3: Install new deps**

Run: `cd /home/mayongtao/projects/nodeble && .venv/bin/pip install -e ".[dev]" -q`

- [ ] **Step 4: Verify imports**

Run: `.venv/bin/python -c "from scipy.stats import norm; from sklearn.ensemble import RandomForestClassifier; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/nodeble/backtest/__init__.py
git commit -m "feat: add backtest package with scipy and scikit-learn deps"
```

---

### Task 2: Black-Scholes pricing module

**Files:**
- Create: `src/nodeble/backtest/pricing.py`
- Create: `tests/test_pricing.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_pricing.py
import math
from nodeble.backtest.pricing import bs_price, bs_delta, find_strike_for_delta


def test_bs_call_price_atm():
    """ATM call with 30 DTE should have reasonable price."""
    price = bs_price(S=500.0, K=500.0, T=30/365, r=0.05, sigma=0.20, option_type="call")
    # ATM call ~$11-13 for SPY at 20% vol, 30 DTE
    assert 8.0 < price < 18.0


def test_bs_put_price_atm():
    """ATM put with 30 DTE should have reasonable price."""
    price = bs_price(S=500.0, K=500.0, T=30/365, r=0.05, sigma=0.20, option_type="put")
    assert 8.0 < price < 18.0


def test_bs_call_price_otm():
    """OTM call should be cheaper than ATM."""
    atm = bs_price(S=500.0, K=500.0, T=30/365, r=0.05, sigma=0.20, option_type="call")
    otm = bs_price(S=500.0, K=520.0, T=30/365, r=0.05, sigma=0.20, option_type="call")
    assert otm < atm


def test_bs_put_price_otm():
    """OTM put should be cheaper than ATM."""
    atm = bs_price(S=500.0, K=500.0, T=30/365, r=0.05, sigma=0.20, option_type="put")
    otm = bs_price(S=500.0, K=480.0, T=30/365, r=0.05, sigma=0.20, option_type="put")
    assert otm < atm


def test_bs_price_zero_time():
    """At expiration, option = intrinsic value."""
    # ITM call: S=500, K=490 → intrinsic = 10
    price = bs_price(S=500.0, K=490.0, T=0.0001, r=0.05, sigma=0.20, option_type="call")
    assert abs(price - 10.0) < 0.5
    # OTM call: S=500, K=510 → intrinsic = 0
    price = bs_price(S=500.0, K=510.0, T=0.0001, r=0.05, sigma=0.20, option_type="call")
    assert price < 0.5


def test_bs_delta_call_atm():
    """ATM call delta should be ~0.50."""
    delta = bs_delta(S=500.0, K=500.0, T=30/365, r=0.05, sigma=0.20, option_type="call")
    assert 0.45 < delta < 0.60


def test_bs_delta_put_atm():
    """ATM put delta should be ~-0.50."""
    delta = bs_delta(S=500.0, K=500.0, T=30/365, r=0.05, sigma=0.20, option_type="put")
    assert -0.60 < delta < -0.45


def test_bs_delta_otm_call():
    """OTM call delta should be small positive."""
    delta = bs_delta(S=500.0, K=530.0, T=30/365, r=0.05, sigma=0.20, option_type="call")
    assert 0.0 < delta < 0.25


def test_bs_delta_otm_put():
    """OTM put delta should be small negative."""
    delta = bs_delta(S=500.0, K=470.0, T=30/365, r=0.05, sigma=0.20, option_type="put")
    assert -0.25 < delta < 0.0


def test_find_strike_for_delta_put():
    """Find OTM put strike for delta -0.15."""
    strike = find_strike_for_delta(
        S=500.0, T=30/365, r=0.05, sigma=0.20,
        target_delta=0.15, option_type="put",
    )
    # Verify the strike produces approximately the target delta
    actual_delta = abs(bs_delta(S=500.0, K=strike, T=30/365, r=0.05, sigma=0.20, option_type="put"))
    assert abs(actual_delta - 0.15) < 0.02
    assert strike < 500.0  # OTM put is below current price
    assert strike == round(strike)  # rounded to $1


def test_find_strike_for_delta_call():
    """Find OTM call strike for delta 0.15."""
    strike = find_strike_for_delta(
        S=500.0, T=30/365, r=0.05, sigma=0.20,
        target_delta=0.15, option_type="call",
    )
    actual_delta = bs_delta(S=500.0, K=strike, T=30/365, r=0.05, sigma=0.20, option_type="call")
    assert abs(actual_delta - 0.15) < 0.02
    assert strike > 500.0  # OTM call is above current price
    assert strike == round(strike)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_pricing.py -v 2>&1 | tail -5`
Expected: FAIL

- [ ] **Step 3: Implement pricing.py**

```python
# src/nodeble/backtest/pricing.py
"""Black-Scholes option pricing for backtest simulation."""
import math
from scipy.stats import norm

RISK_FREE_RATE = 0.05


def bs_price(S: float, K: float, T: float, r: float, sigma: float, option_type: str) -> float:
    """Black-Scholes European option price.

    Args:
        S: underlying price
        K: strike price
        T: time to expiry in years (DTE / 365)
        r: risk-free rate
        sigma: annualized volatility
        option_type: "call" or "put"
    """
    if T <= 0:
        # At expiration: intrinsic value
        if option_type == "call":
            return max(S - K, 0.0)
        else:
            return max(K - S, 0.0)

    if sigma <= 0:
        return max(S - K, 0.0) if option_type == "call" else max(K - S, 0.0)

    d1 = (math.log(S / K) + (r + sigma**2 / 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    if option_type == "call":
        return S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    else:
        return K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def bs_delta(S: float, K: float, T: float, r: float, sigma: float, option_type: str) -> float:
    """Black-Scholes delta.

    Returns:
        Call delta: 0 to 1
        Put delta: -1 to 0
    """
    if T <= 0 or sigma <= 0:
        if option_type == "call":
            return 1.0 if S > K else 0.0
        else:
            return -1.0 if S < K else 0.0

    d1 = (math.log(S / K) + (r + sigma**2 / 2) * T) / (sigma * math.sqrt(T))

    if option_type == "call":
        return norm.cdf(d1)
    else:
        return norm.cdf(d1) - 1.0


def find_strike_for_delta(
    S: float, T: float, r: float, sigma: float,
    target_delta: float, option_type: str,
) -> float:
    """Binary search for strike where |BS delta| ≈ target_delta.

    target_delta should be positive (e.g., 0.15 for a 15-delta option).
    Returns strike rounded to nearest $1.
    """
    if option_type == "put":
        # Put: strike below S, delta is negative
        low, high = S * 0.5, S
        for _ in range(100):
            mid = (low + high) / 2
            d = abs(bs_delta(S, mid, T, r, sigma, "put"))
            if d < target_delta:
                high = mid  # strike too far OTM, move closer
            else:
                low = mid   # strike too close, move further OTM
        return round(mid)
    else:
        # Call: strike above S, delta is positive
        low, high = S, S * 1.5
        for _ in range(100):
            mid = (low + high) / 2
            d = bs_delta(S, mid, T, r, sigma, "call")
            if d > target_delta:
                low = mid   # strike too close, move further OTM
            else:
                high = mid  # strike too far OTM, move closer
        return round(mid)
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_pricing.py -v`
Expected: 12 passed

- [ ] **Step 5: Commit**

```bash
git add src/nodeble/backtest/pricing.py tests/test_pricing.py
git commit -m "feat: add Black-Scholes pricing module for backtest"
```

---

### Task 3: Data fetching and caching

**Files:**
- Create: `src/nodeble/backtest/data.py`

- [ ] **Step 1: Implement data.py**

```python
# src/nodeble/backtest/data.py
"""Fetch and cache historical data for backtesting."""
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

from nodeble.paths import get_data_dir

logger = logging.getLogger(__name__)

CACHE_DIR = None  # set lazily


def _get_cache_dir() -> Path:
    global CACHE_DIR
    if CACHE_DIR is None:
        CACHE_DIR = get_data_dir() / "data" / "backtest"
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR


@dataclass
class BacktestData:
    ohlcv: dict[str, pd.DataFrame]
    vix: pd.Series
    vix9d: pd.Series


def _fetch_and_cache(ticker: str, filename: str, start: str, end: str, force: bool = False) -> pd.DataFrame:
    """Fetch from yfinance, cache to Parquet."""
    cache_path = _get_cache_dir() / filename

    if cache_path.exists() and not force:
        age_hours = (pd.Timestamp.now() - pd.Timestamp(cache_path.stat().st_mtime, unit="s")).total_seconds() / 3600
        if age_hours < 24:
            logger.info(f"Using cached {filename} ({age_hours:.1f}h old)")
            return pd.read_parquet(cache_path)

    logger.info(f"Fetching {ticker} from yfinance ({start} to {end})...")
    t = yf.Ticker(ticker)
    df = t.history(start=start, end=end, auto_adjust=True)

    if df.empty:
        logger.warning(f"No data returned for {ticker}")
        return pd.DataFrame()

    # Normalize columns
    col_map = {"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
    df = df.rename(columns=col_map)
    cols = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
    df = df[cols]
    df.index = df.index.tz_localize(None)
    df.index.name = "date"

    df.to_parquet(cache_path)
    logger.info(f"Cached {len(df)} rows to {filename}")
    return df


def load_backtest_data(symbols: list[str], years: int = 5, force_fetch: bool = False) -> BacktestData:
    """Load all data needed for backtesting."""
    end = date.today()
    start = end - timedelta(days=int(years * 365.25 + 60))  # extra padding
    start_str = str(start)
    end_str = str(end)

    # OHLCV per symbol
    ohlcv = {}
    for sym in symbols:
        df = _fetch_and_cache(sym, f"{sym}_ohlcv.parquet", start_str, end_str, force_fetch)
        if not df.empty:
            ohlcv[sym] = df
        else:
            logger.warning(f"No data for {sym}, skipping")

    # VIX
    vix_df = _fetch_and_cache("^VIX", "VIX_daily.parquet", start_str, end_str, force_fetch)
    vix = vix_df["close"] if not vix_df.empty and "close" in vix_df.columns else pd.Series(dtype=float)

    # VIX9D
    vix9d_df = _fetch_and_cache("^VIX9D", "VIX9D_daily.parquet", start_str, end_str, force_fetch)
    vix9d = vix9d_df["close"] if not vix9d_df.empty and "close" in vix9d_df.columns else pd.Series(dtype=float)

    logger.info(f"Loaded backtest data: {len(ohlcv)} symbols, VIX {len(vix)} days, VIX9D {len(vix9d)} days")
    return BacktestData(ohlcv=ohlcv, vix=vix, vix9d=vix9d)
```

- [ ] **Step 2: Verify it works**

Run: `.venv/bin/python -c "from nodeble.backtest.data import load_backtest_data; d = load_backtest_data(['SPY'], years=1); print(f'SPY: {len(d.ohlcv[\"SPY\"])} rows, VIX: {len(d.vix)} rows')"`
Expected: `SPY: ~252 rows, VIX: ~252 rows`

- [ ] **Step 3: Commit**

```bash
git add src/nodeble/backtest/data.py
git commit -m "feat: add backtest data fetcher with Parquet caching"
```

---

### Task 4: Simulator — day-by-day IC simulation

**Files:**
- Create: `src/nodeble/backtest/simulator.py`
- Create: `tests/test_simulator.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_simulator.py
import pandas as pd
import numpy as np
from datetime import date, timedelta
from nodeble.backtest.simulator import (
    BacktestParams, BacktestPosition, TradeResult,
    simulate_ic, compute_metrics,
)


def _make_flat_ohlcv(start_price=500.0, days=300, daily_move=0.001):
    """Generate flat/slightly-moving OHLCV data."""
    dates = pd.bdate_range(start="2021-01-04", periods=days)
    prices = [start_price]
    for i in range(1, days):
        prices.append(prices[-1] * (1 + np.random.uniform(-daily_move, daily_move)))
    prices = np.array(prices)
    return pd.DataFrame({
        "open": prices * 0.999,
        "high": prices * 1.005,
        "low": prices * 0.995,
        "close": prices,
        "volume": np.full(days, 1_000_000),
    }, index=dates)


def _make_vix_series(days=300, level=18.0):
    """Generate flat VIX series."""
    dates = pd.bdate_range(start="2021-01-04", periods=days)
    return pd.Series(np.full(days, level), index=dates)


def test_simulate_produces_trades():
    """Basic simulation should produce at least one trade."""
    ohlcv = _make_flat_ohlcv(days=400)
    vix = _make_vix_series(days=400)
    vix9d = _make_vix_series(days=400, level=17.0)
    params = BacktestParams(use_adaptive=False, use_indicators=False, dte=30, cooldown_days=5)
    results = simulate_ic("SPY", ohlcv, vix, vix9d, params)
    assert len(results) > 0
    assert all(isinstance(r, TradeResult) for r in results)


def test_flat_market_mostly_wins():
    """In a flat market, ICs should mostly win."""
    ohlcv = _make_flat_ohlcv(days=500, daily_move=0.002)
    vix = _make_vix_series(days=500)
    vix9d = _make_vix_series(days=500, level=17.0)
    params = BacktestParams(
        use_adaptive=False, use_indicators=False,
        put_delta=0.10, call_delta=0.10, dte=30,
        profit_target_pct=0.50, cooldown_days=5,
    )
    results = simulate_ic("SPY", ohlcv, vix, vix9d, params)
    wins = sum(1 for r in results if r.pnl > 0)
    assert wins / len(results) > 0.5 if results else True


def test_trade_result_fields():
    """TradeResult should have all expected fields."""
    ohlcv = _make_flat_ohlcv(days=400)
    vix = _make_vix_series(days=400)
    vix9d = _make_vix_series(days=400, level=17.0)
    params = BacktestParams(use_adaptive=False, use_indicators=False, dte=30)
    results = simulate_ic("SPY", ohlcv, vix, vix9d, params)
    if results:
        r = results[0]
        assert r.position.symbol == "SPY"
        assert r.exit_reason in ("profit_target", "stop_loss", "dte_close", "expiration", "end_of_data")
        assert isinstance(r.pnl, float)
        assert r.days_held > 0


def test_compute_metrics():
    """Metrics computation from trade results."""
    ohlcv = _make_flat_ohlcv(days=500)
    vix = _make_vix_series(days=500)
    vix9d = _make_vix_series(days=500, level=17.0)
    params = BacktestParams(use_adaptive=False, use_indicators=False, dte=30)
    results = simulate_ic("SPY", ohlcv, vix, vix9d, params)
    if results:
        metrics = compute_metrics(results)
        assert "total_trades" in metrics
        assert "win_rate" in metrics
        assert "total_pnl" in metrics
        assert "sharpe_ratio" in metrics
        assert metrics["total_trades"] == len(results)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_simulator.py -v 2>&1 | tail -5`
Expected: FAIL

- [ ] **Step 3: Implement simulator.py**

```python
# src/nodeble/backtest/simulator.py
"""Day-by-day iron condor simulation engine."""
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd

from nodeble.backtest.pricing import bs_price, bs_delta, find_strike_for_delta, RISK_FREE_RATE

logger = logging.getLogger(__name__)

WARMUP_DAYS = 252


@dataclass
class BacktestParams:
    put_delta: float = 0.15
    call_delta: float = 0.15
    dte: int = 30
    spread_width: float = 10.0
    profit_target_pct: float = 0.50
    stop_loss_pct: float = 2.0
    close_before_dte: int = 3
    cooldown_days: int = 5
    use_adaptive: bool = True
    use_indicators: bool = True


@dataclass
class BacktestPosition:
    symbol: str
    entry_date: date
    expiry_date: date
    entry_dte: int
    short_put_strike: float
    long_put_strike: float
    short_call_strike: float
    long_call_strike: float
    entry_credit: float
    entry_vix: float
    entry_vix9d: float | None = None
    entry_term_ratio: float | None = None
    entry_bull_share: float = 0.50
    entry_indicator_votes: dict = field(default_factory=dict)


@dataclass
class TradeResult:
    position: BacktestPosition
    exit_date: date
    exit_value: float
    pnl: float
    pnl_pct: float
    exit_reason: str
    max_adverse_excursion: float
    days_held: int


def _price_ic(S: float, pos: BacktestPosition, dte_remaining: int, sigma: float) -> float:
    """Price the IC (cost to close) using Black-Scholes."""
    T = max(dte_remaining, 0) / 365.0
    if T <= 0:
        # At expiration: intrinsic values
        sp = max(pos.short_put_strike - S, 0.0)
        lp = max(pos.long_put_strike - S, 0.0)
        sc = max(S - pos.short_call_strike, 0.0)
        lc = max(S - pos.long_call_strike, 0.0)
        return (sp - lp) + (sc - lc)

    r = RISK_FREE_RATE
    sp = bs_price(S, pos.short_put_strike, T, r, sigma, "put")
    lp = bs_price(S, pos.long_put_strike, T, r, sigma, "put")
    sc = bs_price(S, pos.short_call_strike, T, r, sigma, "call")
    lc = bs_price(S, pos.long_call_strike, T, r, sigma, "call")
    # Cost to close = buy back shorts - sell longs
    return (sp - lp) + (sc - lc)


def simulate_ic(
    symbol: str,
    ohlcv: pd.DataFrame,
    vix: pd.Series,
    vix9d: pd.Series,
    params: BacktestParams,
    adaptive_config: dict | None = None,
) -> list[TradeResult]:
    """Run day-by-day IC simulation on historical data.

    Returns list of completed trades.
    """
    results: list[TradeResult] = []
    position: BacktestPosition | None = None
    last_close_idx = -params.cooldown_days - 1
    max_adverse = 0.0

    dates = ohlcv.index
    if len(dates) < WARMUP_DAYS + 30:
        logger.warning(f"{symbol}: Not enough data ({len(dates)} days, need {WARMUP_DAYS + 30})")
        return results

    # Pre-compute indicators if needed
    indicator_cache = {}
    if params.use_indicators:
        try:
            from nodeble.signals.registry import get_all_indicators
            from nodeble.signals.scorer import VotingEngine
            indicators = get_all_indicators()
            engine = VotingEngine()
            for i in range(WARMUP_DAYS, len(dates)):
                window = ohlcv.iloc[max(0, i - WARMUP_DAYS):i + 1]
                result = engine.score(symbol, window, indicators)
                indicator_cache[dates[i]] = {
                    "bull_share": result.bull_share,
                    "votes": result.votes,
                }
        except Exception as e:
            logger.warning(f"Indicator computation failed: {e}. Running without indicators.")
            params.use_indicators = False

    for i in range(WARMUP_DAYS, len(dates)):
        today = dates[i]
        today_date = today.date() if hasattr(today, "date") else today
        price = float(ohlcv.iloc[i]["close"])
        day_high = float(ohlcv.iloc[i]["high"])
        day_low = float(ohlcv.iloc[i]["low"])

        # Get VIX for today
        current_vix = float(vix.get(today, 20.0)) if today in vix.index else 20.0
        current_vix9d = float(vix9d.get(today, 0.0)) if today in vix9d.index else None
        if current_vix9d == 0.0:
            current_vix9d = None
        sigma = current_vix / 100.0

        # Compute term ratio
        term_ratio = None
        if current_vix9d is not None and current_vix > 0:
            term_ratio = current_vix9d / current_vix

        # Get indicator signal
        bull_share = 0.50
        indicator_votes = {}
        if params.use_indicators and today in indicator_cache:
            bull_share = indicator_cache[today]["bull_share"]
            indicator_votes = indicator_cache[today]["votes"]

        # Determine deltas and DTE
        put_delta = params.put_delta
        call_delta = params.call_delta
        target_dte = params.dte

        if params.use_adaptive and adaptive_config:
            try:
                from nodeble.strategy.adaptive import compute_adaptive_params
                sel = {
                    "put_delta_min": params.put_delta * 0.5,
                    "put_delta_max": params.put_delta,
                    "call_delta_min": params.call_delta * 0.5,
                    "call_delta_max": params.call_delta,
                }
                adjusted = compute_adaptive_params(
                    bull_share, current_vix, sel, adaptive_config, term_ratio=term_ratio,
                )
                put_delta = (adjusted["put_delta_min"] + adjusted["put_delta_max"]) / 2
                call_delta = (adjusted["call_delta_min"] + adjusted["call_delta_max"]) / 2
                target_dte = adjusted["dte_ideal"]
            except Exception as e:
                logger.debug(f"Adaptive failed on {today}: {e}")

        # --- Position Management ---
        if position is not None:
            dte_remaining = (position.expiry_date - today_date).days
            current_value = _price_ic(price, position, dte_remaining, sigma)

            # Track max adverse excursion
            unrealized_pnl = position.entry_credit - current_value
            if unrealized_pnl < max_adverse:
                max_adverse = unrealized_pnl

            # Check exit conditions
            exit_reason = None

            if current_value <= position.entry_credit * params.profit_target_pct:
                exit_reason = "profit_target"
            elif current_value >= position.entry_credit * params.stop_loss_pct:
                exit_reason = "stop_loss"
            elif dte_remaining <= params.close_before_dte:
                exit_reason = "dte_close"
            elif dte_remaining <= 0:
                exit_reason = "expiration"

            if exit_reason:
                pnl = position.entry_credit - current_value
                max_risk = params.spread_width
                results.append(TradeResult(
                    position=position,
                    exit_date=today_date,
                    exit_value=current_value,
                    pnl=pnl,
                    pnl_pct=pnl / max_risk if max_risk > 0 else 0.0,
                    exit_reason=exit_reason,
                    max_adverse_excursion=max_adverse,
                    days_held=(today_date - position.entry_date).days,
                ))
                position = None
                last_close_idx = i
                max_adverse = 0.0
            continue

        # --- Entry Logic ---
        if (i - last_close_idx) < params.cooldown_days:
            continue

        if sigma <= 0:
            continue

        T = target_dte / 365.0
        if T <= 0:
            continue

        try:
            short_put = find_strike_for_delta(price, T, RISK_FREE_RATE, sigma, put_delta, "put")
            short_call = find_strike_for_delta(price, T, RISK_FREE_RATE, sigma, call_delta, "call")
            long_put = short_put - params.spread_width
            long_call = short_call + params.spread_width

            # Price the IC at entry
            entry_credit = _price_ic(price, BacktestPosition(
                symbol=symbol, entry_date=today_date,
                expiry_date=today_date + timedelta(days=target_dte),
                entry_dte=target_dte,
                short_put_strike=short_put, long_put_strike=long_put,
                short_call_strike=short_call, long_call_strike=long_call,
                entry_credit=0.0, entry_vix=current_vix,
            ), target_dte, sigma)

            if entry_credit <= 0:
                continue

            position = BacktestPosition(
                symbol=symbol,
                entry_date=today_date,
                expiry_date=today_date + timedelta(days=target_dte),
                entry_dte=target_dte,
                short_put_strike=short_put,
                long_put_strike=long_put,
                short_call_strike=short_call,
                long_call_strike=long_call,
                entry_credit=entry_credit,
                entry_vix=current_vix,
                entry_vix9d=current_vix9d,
                entry_term_ratio=term_ratio,
                entry_bull_share=bull_share,
                entry_indicator_votes=indicator_votes,
            )
            max_adverse = 0.0
            logger.debug(
                f"{symbol} {today_date}: OPEN IC put={short_put}/{long_put} "
                f"call={short_call}/{long_call} credit={entry_credit:.2f} DTE={target_dte}"
            )
        except Exception as e:
            logger.debug(f"Entry failed on {today}: {e}")

    # Close any remaining position at last day
    if position is not None:
        last_price = float(ohlcv.iloc[-1]["close"])
        last_date = dates[-1].date() if hasattr(dates[-1], "date") else dates[-1]
        dte_remaining = max((position.expiry_date - last_date).days, 0)
        current_value = _price_ic(last_price, position, dte_remaining, sigma)
        pnl = position.entry_credit - current_value
        max_risk = params.spread_width
        results.append(TradeResult(
            position=position, exit_date=last_date, exit_value=current_value,
            pnl=pnl, pnl_pct=pnl / max_risk if max_risk > 0 else 0.0,
            exit_reason="end_of_data", max_adverse_excursion=max_adverse,
            days_held=(last_date - position.entry_date).days,
        ))

    logger.info(f"{symbol}: {len(results)} trades simulated")
    return results


def compute_metrics(results: list[TradeResult]) -> dict:
    """Compute standard backtest metrics from trade results."""
    if not results:
        return {
            "total_trades": 0, "win_rate": 0.0, "total_pnl": 0.0,
            "avg_win": 0.0, "avg_loss": 0.0, "max_drawdown": 0.0, "sharpe_ratio": 0.0,
        }

    pnls = [r.pnl for r in results]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]

    # Max drawdown from cumulative P&L
    cum_pnl = np.cumsum(pnls)
    peak = np.maximum.accumulate(cum_pnl)
    drawdown = peak - cum_pnl
    max_dd = float(np.max(drawdown)) if len(drawdown) > 0 else 0.0

    # Sharpe: annualized from per-trade returns
    pnl_arr = np.array(pnls)
    sharpe = 0.0
    if len(pnl_arr) > 1 and np.std(pnl_arr) > 0:
        trades_per_year = len(results) / 5.0  # rough estimate
        sharpe = float(np.mean(pnl_arr) / np.std(pnl_arr) * np.sqrt(max(trades_per_year, 1)))

    return {
        "total_trades": len(results),
        "win_rate": len(wins) / len(results) if results else 0.0,
        "total_pnl": sum(pnls),
        "avg_win": sum(wins) / len(wins) if wins else 0.0,
        "avg_loss": sum(losses) / len(losses) if losses else 0.0,
        "max_drawdown": max_dd,
        "sharpe_ratio": round(sharpe, 3),
    }
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/test_simulator.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/nodeble/backtest/simulator.py tests/test_simulator.py
git commit -m "feat: add IC simulator with day-by-day BS pricing"
```

---

### Task 5: Parameter sweep

**Files:**
- Create: `src/nodeble/backtest/sweep.py`

- [ ] **Step 1: Implement sweep.py**

```python
# src/nodeble/backtest/sweep.py
"""Parameter sweep: grid search across IC parameter combinations."""
import csv
import itertools
import logging
from pathlib import Path

import pandas as pd

from nodeble.backtest.simulator import BacktestParams, simulate_ic, compute_metrics
from nodeble.paths import get_data_dir

logger = logging.getLogger(__name__)

SWEEP_DEFAULTS = {
    "delta": [0.08, 0.10, 0.12, 0.15, 0.20, 0.25],
    "dte": [7, 14, 21, 30, 45],
    "profit_target": [0.25, 0.40, 0.50, 0.60, 0.75],
    "spread_width": [5, 10],
}


def run_sweep(
    symbol: str,
    ohlcv: pd.DataFrame,
    vix: pd.Series,
    vix9d: pd.Series,
    sweep_config: dict | None = None,
) -> list[dict]:
    """Run parameter sweep for a single symbol.

    Returns list of dicts, each with params + metrics.
    """
    grid = sweep_config or SWEEP_DEFAULTS
    deltas = grid.get("delta", SWEEP_DEFAULTS["delta"])
    dtes = grid.get("dte", SWEEP_DEFAULTS["dte"])
    targets = grid.get("profit_target", SWEEP_DEFAULTS["profit_target"])
    widths = grid.get("spread_width", SWEEP_DEFAULTS["spread_width"])

    combos = list(itertools.product(deltas, dtes, targets, widths))
    total = len(combos)
    logger.info(f"Sweep: {total} combinations for {symbol}")

    all_results = []
    for idx, (delta, dte, target, width) in enumerate(combos, 1):
        if idx % 50 == 0 or idx == 1:
            logger.info(f"  Sweep progress: {idx}/{total}")

        params = BacktestParams(
            put_delta=delta,
            call_delta=delta,  # symmetric for sweep
            dte=dte,
            spread_width=width,
            profit_target_pct=target,
            use_adaptive=False,
            use_indicators=False,
        )

        trades = simulate_ic(symbol, ohlcv, vix, vix9d, params)
        metrics = compute_metrics(trades)

        row = {
            "symbol": symbol,
            "delta": delta,
            "dte": dte,
            "profit_target": target,
            "spread_width": width,
            **metrics,
        }
        all_results.append(row)

    # Sort by Sharpe ratio
    all_results.sort(key=lambda r: r.get("sharpe_ratio", 0), reverse=True)
    return all_results


def save_sweep_results(results: list[dict], filename: str = "sweep_results.csv"):
    """Save sweep results to CSV."""
    if not results:
        return

    out_dir = get_data_dir() / "data" / "backtest"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename

    fieldnames = list(results[0].keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    logger.info(f"Sweep results saved to {path}")


def print_top_results(results: list[dict], top_n: int = 10):
    """Print top N results to console."""
    print(f"\n{'='*80}")
    print(f"  TOP {top_n} PARAMETER COMBINATIONS (by Sharpe Ratio)")
    print(f"{'='*80}")
    print(f"{'Rank':<5} {'Delta':<7} {'DTE':<5} {'Target':<8} {'Width':<6} "
          f"{'Trades':<7} {'WinRate':<8} {'P&L':<10} {'MaxDD':<8} {'Sharpe':<7}")
    print("-" * 80)

    for i, r in enumerate(results[:top_n], 1):
        print(f"{i:<5} {r['delta']:<7.2f} {r['dte']:<5} {r['profit_target']:<8.2f} "
              f"{r['spread_width']:<6.0f} {r['total_trades']:<7} "
              f"{r['win_rate']:<8.1%} ${r['total_pnl']:<9.2f} "
              f"${r['max_drawdown']:<7.2f} {r['sharpe_ratio']:<7.3f}")
    print(f"{'='*80}\n")
```

- [ ] **Step 2: Verify import**

Run: `.venv/bin/python -c "from nodeble.backtest.sweep import run_sweep; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/nodeble/backtest/sweep.py
git commit -m "feat: add parameter sweep grid search for backtest"
```

---

### Task 6: Feature importance analysis

**Files:**
- Create: `src/nodeble/backtest/analysis.py`

- [ ] **Step 1: Implement analysis.py**

```python
# src/nodeble/backtest/analysis.py
"""Feature importance analysis using Random Forest on backtest trade results."""
import logging
from pathlib import Path

import numpy as np

from nodeble.backtest.simulator import TradeResult
from nodeble.paths import get_data_dir

logger = logging.getLogger(__name__)

# Indicator categories for grouping
INDICATOR_CATEGORIES = {
    "sma_50_200_cross": "trend", "ema_12_26_cross": "trend", "adx_trend": "trend",
    "supertrend": "trend", "aroon_oscillator": "trend",
    "rsi_14": "momentum", "macd_histogram": "momentum", "stochastic_kd": "momentum",
    "cci_20": "momentum", "williams_r": "momentum",
    "bollinger_position": "volatility", "keltner_channel": "volatility", "atr_trend": "volatility",
    "donchian_channel": "volatility", "bollinger_width": "volatility",
    "obv_trend": "volume", "mfi_14": "volume", "cmf_20": "volume",
    "vwap_distance": "volume", "volume_sma_ratio": "volume",
}


def run_feature_importance(results: list[TradeResult]) -> dict:
    """Run Random Forest feature importance analysis on trade results.

    Returns dict with importances, cv_scores, and recommendations.
    """
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import cross_val_score

    # Build feature matrix
    feature_names = []
    X_rows = []
    y = []

    for r in results:
        votes = r.position.entry_indicator_votes
        if not votes:
            continue

        if not feature_names:
            indicator_names = sorted(votes.keys())
            feature_names = indicator_names + ["vix", "vix9d", "term_ratio", "bull_share"]

        row = [votes.get(name, 0) for name in feature_names[:-4]]  # use established names, not current trade's keys
        row.append(r.position.entry_vix)
        row.append(r.position.entry_vix9d or 0.0)
        row.append(r.position.entry_term_ratio or 0.0)
        row.append(r.position.entry_bull_share)
        X_rows.append(row)
        y.append(1 if r.pnl > 0 else 0)

    if len(X_rows) < 50:
        logger.warning(f"Only {len(X_rows)} trades with indicator data — results may be unreliable (need 100+)")

    if len(X_rows) < 20:
        logger.error("Too few trades for meaningful analysis (<20). Skipping.")
        return {}

    X = np.array(X_rows)
    y = np.array(y)

    # Cross-validation
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    cv_folds = min(5, len(X_rows) // 10) or 2
    cv_scores = cross_val_score(model, X, y, cv=cv_folds)

    # Fit full model for importances
    model.fit(X, y)
    importances = dict(zip(feature_names, model.feature_importances_))

    # Sort by importance
    sorted_imp = sorted(importances.items(), key=lambda x: x[1], reverse=True)

    # Category breakdown
    cat_totals = {}
    for name, imp in importances.items():
        cat = INDICATOR_CATEGORIES.get(name, "market")
        cat_totals[cat] = cat_totals.get(cat, 0.0) + imp

    # Recommendations
    keep = [name for name, imp in sorted_imp if imp >= 0.05 and name in INDICATOR_CATEGORIES]
    drop = [name for name, imp in sorted_imp if imp < 0.02 and name in INDICATOR_CATEGORIES]

    return {
        "importances": sorted_imp,
        "cv_accuracy": float(np.mean(cv_scores)),
        "cv_std": float(np.std(cv_scores)),
        "category_breakdown": cat_totals,
        "keep": keep,
        "drop": drop,
        "total_trades": len(X_rows),
    }


def print_importance_report(analysis: dict):
    """Print feature importance report to console."""
    if not analysis:
        print("No analysis results available.")
        return

    print(f"\n{'='*60}")
    print(f"  INDICATOR FEATURE IMPORTANCE")
    print(f"{'='*60}")
    print(f"{'Rank':<5} {'Indicator':<25} {'Importance':<12} {'Category':<12}")
    print("-" * 60)

    for i, (name, imp) in enumerate(analysis["importances"], 1):
        cat = INDICATOR_CATEGORIES.get(name, "market")
        marker = " *" if imp >= 0.05 else " x" if imp < 0.02 and name in INDICATOR_CATEGORIES else ""
        print(f"{i:<5} {name:<25} {imp:<12.4f} {cat:<12}{marker}")

    print(f"\nCross-validation accuracy: {analysis['cv_accuracy']:.2f} (+/- {analysis['cv_std']:.2f})")
    print(f"Total trades analyzed: {analysis['total_trades']}")

    print(f"\nCategory breakdown:")
    for cat, total in sorted(analysis["category_breakdown"].items(), key=lambda x: x[1], reverse=True):
        count = sum(1 for n in INDICATOR_CATEGORIES.values() if n == cat) if cat != "market" else 4
        print(f"  {cat:<12} {total:.2f} ({count} features)")

    if analysis["keep"]:
        print(f"\nKEEP (importance >= 0.05): {', '.join(analysis['keep'])}")
    if analysis["drop"]:
        print(f"DROP (importance < 0.02):  {', '.join(analysis['drop'])}")
    print(f"{'='*60}\n")


def save_importance_report(analysis: dict, filename: str = "feature_importance.txt"):
    """Save report to file."""
    if not analysis:
        return

    out_dir = get_data_dir() / "data" / "backtest"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename

    import io
    import sys
    old_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()
    print_importance_report(analysis)
    sys.stdout = old_stdout
    path.write_text(buffer.getvalue())
    logger.info(f"Feature importance report saved to {path}")
```

- [ ] **Step 2: Verify import**

Run: `.venv/bin/python -c "from nodeble.backtest.analysis import run_feature_importance; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/nodeble/backtest/analysis.py
git commit -m "feat: add Random Forest feature importance analysis"
```

---

### Task 7: Runner (orchestrator) and CLI integration

**Files:**
- Create: `src/nodeble/backtest/runner.py`
- Modify: `src/nodeble/__main__.py`

- [ ] **Step 1: Implement runner.py**

```python
# src/nodeble/backtest/runner.py
"""Backtest orchestrator: data loading → simulation → sweep → analysis."""
import logging

from nodeble.backtest.data import load_backtest_data
from nodeble.backtest.simulator import BacktestParams, simulate_ic, compute_metrics
from nodeble.backtest.sweep import run_sweep, save_sweep_results, print_top_results
from nodeble.backtest.analysis import run_feature_importance, print_importance_report, save_importance_report

logger = logging.getLogger(__name__)


def run_backtest(
    symbols: list[str],
    years: int = 5,
    force_fetch: bool = False,
    do_sweep: bool = False,
    do_analyze: bool = False,
    strategy_cfg: dict | None = None,
):
    """Main backtest entry point."""
    # 1. Load data
    print(f"\nLoading {years} years of data for {', '.join(symbols)}...")
    data = load_backtest_data(symbols, years=years, force_fetch=force_fetch)

    if not data.ohlcv:
        print("ERROR: No data loaded. Check symbols and network connection.")
        return

    # 2. Parameter sweep
    if do_sweep:
        sweep_cfg = None
        if strategy_cfg:
            sweep_cfg = strategy_cfg.get("backtest", {}).get("sweep")

        for symbol in symbols:
            if symbol not in data.ohlcv:
                continue
            print(f"\nRunning parameter sweep for {symbol}...")
            results = run_sweep(symbol, data.ohlcv[symbol], data.vix, data.vix9d, sweep_cfg)
            save_sweep_results(results, f"sweep_{symbol}.csv")
            print_top_results(results)
        return

    # 3. Single run (with optional analysis)
    adaptive_cfg = strategy_cfg.get("adaptive", {}) if strategy_cfg else None
    params = BacktestParams(use_adaptive=bool(adaptive_cfg), use_indicators=True)

    # Override from strategy config if available
    if strategy_cfg:
        sel = strategy_cfg.get("selection", {})
        mgmt = strategy_cfg.get("management", {})
        params.put_delta = sel.get("put_delta_max", params.put_delta)
        params.call_delta = sel.get("call_delta_max", params.call_delta)
        params.dte = sel.get("dte_ideal", sel.get("dte_max", params.dte))
        params.spread_width = 10.0  # default
        params.profit_target_pct = mgmt.get("profit_take_pct", params.profit_target_pct)
        params.stop_loss_pct = mgmt.get("stop_loss_pct", params.stop_loss_pct)
        params.close_before_dte = mgmt.get("close_before_dte", params.close_before_dte)

    all_trades = []
    for symbol in symbols:
        if symbol not in data.ohlcv:
            continue
        print(f"\nSimulating {symbol}...")
        trades = simulate_ic(
            symbol, data.ohlcv[symbol], data.vix, data.vix9d,
            params, adaptive_config=adaptive_cfg,
        )
        all_trades.extend(trades)
        metrics = compute_metrics(trades)

        print(f"\n  {symbol} Results:")
        print(f"    Trades: {metrics['total_trades']}")
        print(f"    Win rate: {metrics['win_rate']:.1%}")
        print(f"    Total P&L: ${metrics['total_pnl']:.2f}")
        print(f"    Avg win: ${metrics['avg_win']:.2f}")
        print(f"    Avg loss: ${metrics['avg_loss']:.2f}")
        print(f"    Max drawdown: ${metrics['max_drawdown']:.2f}")
        print(f"    Sharpe ratio: {metrics['sharpe_ratio']:.3f}")

    # 4. Feature importance
    if do_analyze and all_trades:
        print(f"\nRunning feature importance analysis on {len(all_trades)} trades...")
        analysis = run_feature_importance(all_trades)
        print_importance_report(analysis)
        save_importance_report(analysis)

    # Combined metrics
    if len(symbols) > 1 and all_trades:
        combined = compute_metrics(all_trades)
        print(f"\n  COMBINED Results ({len(symbols)} symbols):")
        print(f"    Trades: {combined['total_trades']}")
        print(f"    Win rate: {combined['win_rate']:.1%}")
        print(f"    Total P&L: ${combined['total_pnl']:.2f}")
        print(f"    Sharpe ratio: {combined['sharpe_ratio']:.3f}")
```

- [ ] **Step 2: Add --mode backtest to __main__.py**

Add to the argparser in `main()`:

```python
    parser.add_argument("--sweep", action="store_true", help="Run parameter sweep")
    parser.add_argument("--analyze", action="store_true", help="Run feature importance analysis")
    parser.add_argument("--symbols", default="SPY,QQQ,IWM", help="Comma-separated symbols")
    parser.add_argument("--years", type=int, default=5, help="Years of history")
    parser.add_argument("--force-fetch", action="store_true", help="Re-download data")
```

Update the `--mode` choices:

```python
    parser.add_argument("--mode", choices=["scan", "manage", "signal", "backtest"], help="Run mode")
```

Add backtest handling in `main()`, after the signal mode block:

```python
    if args.mode == "backtest":
        from nodeble.backtest.runner import run_backtest
        symbols = [s.strip() for s in args.symbols.split(",")]
        run_backtest(
            symbols=symbols,
            years=args.years,
            force_fetch=args.force_fetch,
            do_sweep=args.sweep,
            do_analyze=args.analyze,
            strategy_cfg=strategy_cfg,
        )
        return
```

- [ ] **Step 3: Run full test suite**

Run: `.venv/bin/python -m pytest -v 2>&1 | tail -5`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add src/nodeble/backtest/runner.py src/nodeble/__main__.py
git commit -m "feat: add backtest runner and CLI integration"
```

---

### Task 8: End-to-end test and push

- [ ] **Step 1: Run full test suite**

Run: `.venv/bin/python -m pytest -v`
Expected: All tests pass

- [ ] **Step 2: Quick smoke test — single symbol, 1 year**

Run: `.venv/bin/python -m nodeble --mode backtest --symbols SPY --years 1 2>&1 | tail -20`
Expected: Shows trade results with metrics

- [ ] **Step 3: Commit docs and push**

```bash
git add docs/superpowers/
git commit -m "docs: add IC backtest engine spec and plan"
git push origin main
```
