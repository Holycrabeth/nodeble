# IC Backtest Engine — Design Spec

## Goal

Build a backtest engine that simulates 5 years of iron condor trades using historical OHLCV + VIX data, with parameter sweep capability and Random Forest feature importance analysis on the 20 indicators.

## Problem

The 20 trend-following indicators were designed for stock direction, not iron condor range prediction. We need to empirically test which indicators actually predict IC success, find optimal parameter combinations, and validate the adaptive layer's VIX/term structure logic against historical data.

## Architecture

The backtest engine lives inside the nodeble package at `src/nodeble/backtest/`. It reuses the existing indicators, VotingEngine, and adaptive layer directly. No production code changes needed.

```
python -m nodeble --mode backtest              # single run with current config
python -m nodeble --mode backtest --sweep       # parameter sweep (300 combos)
python -m nodeble --mode backtest --analyze     # feature importance analysis
python -m nodeble --mode backtest --sweep --analyze  # both
```

## Data Pipeline

### Fetching

- 5 years daily OHLCV for each symbol (default: SPY, QQQ, IWM) via yfinance
- 5 years daily VIX (`^VIX`) and VIX9D (`^VIX9D`) via yfinance
- Configurable via `--symbols SPY,QQQ` and `--years 5`

### Caching

Data cached to Parquet files in `~/.nodeble/data/backtest/`:
```
~/.nodeble/data/backtest/
├── SPY_ohlcv.parquet
├── QQQ_ohlcv.parquet
├── IWM_ohlcv.parquet
├── VIX_daily.parquet
└── VIX9D_daily.parquet
```

Re-fetch only if cache is older than 24 hours or `--force-fetch` flag is passed.

### Data Structure

```python
@dataclass
class BacktestData:
    ohlcv: dict[str, pd.DataFrame]  # {symbol: DataFrame with OHLCV}
    vix: pd.Series                   # Daily VIX values, DatetimeIndex
    vix9d: pd.Series                 # Daily VIX9D values, DatetimeIndex
```

## Black-Scholes Pricing

### Option Pricing

Standard Black-Scholes for European options:

```python
def bs_price(S, K, T, r, sigma, option_type) -> float:
    """Black-Scholes option price.

    S: underlying price
    K: strike price
    T: time to expiry in years (DTE / 365)
    r: risk-free rate (constant 0.05)
    sigma: annualized volatility (VIX / 100)
    option_type: "call" or "put"
    """
```

### Delta Calculation

```python
def bs_delta(S, K, T, r, sigma, option_type) -> float:
    """Black-Scholes delta for strike selection."""
```

### Strike Selection

Given a target delta, find the strike price:

```python
def find_strike_for_delta(S, T, r, sigma, target_delta, option_type) -> float:
    """Binary search for strike where BS delta ≈ target_delta.

    Returns strike rounded to nearest $1.
    """
```

### Constants

- Risk-free rate: 0.05 (constant approximation)
- Volatility: VIX / 100 for the given day (annualized)
- Strike rounding: nearest $1

## Single Backtest Run (Simulator)

### Parameters

```python
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
    use_adaptive: bool = True       # use adaptive layer for delta/DTE
    use_indicators: bool = True     # use 20 indicators for directional skew
```

When `use_adaptive=True`, the adaptive layer computes delta/DTE from VIX regime + term structure + directional skew, overriding the static `put_delta`, `call_delta`, and `dte` values. When `False`, static values are used (useful for comparing adaptive vs static).

### Day-by-Day Simulation

```
Skip first 252 trading days (indicator warmup).

For each trading day:
  1. Run 20 indicators on trailing 252 days → VoteResult (bull_share)
  2. Get VIX and VIX9D for this day
  3. If use_adaptive: compute adaptive params from VIX + term_ratio + bull_share
     → collapse ranges to point values: put_delta = (put_delta_min + put_delta_max) / 2,
       call_delta = (call_delta_min + call_delta_max) / 2, dte = dte_ideal
     Else: use static params from BacktestParams
  4. If no position open AND cooldown met:
     a. Compute short strikes using find_strike_for_delta()
     b. Compute long strikes: short_put - width, short_call + width
     c. Price all 4 legs using bs_price() → entry credit
     d. If entry credit > 0: open position, record entry details + all 20 indicator votes
  5. If position open:
     a. Reprice all 4 legs with current price, VIX, remaining DTE
     b. current_value = cost to close (buy back shorts at ask estimate, sell longs at bid estimate)
        Simplified: current_value = sum of BS prices of the 4 legs at current conditions
     c. Check profit target: current_value <= entry_credit × profit_target_pct → CLOSE WIN
     d. Check stop loss: current_value >= entry_credit × stop_loss_pct → CLOSE LOSS
     e. Check DTE: remaining DTE <= close_before_dte → CLOSE (P&L determines win/loss)
     f. Check expiration: DTE = 0 → CLOSE at intrinsic value
```

### Position Tracking

```python
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
    entry_vix9d: float | None
    entry_term_ratio: float | None
    entry_bull_share: float
    entry_indicator_votes: dict  # {indicator_name: vote}
```

### Trade Result

```python
@dataclass
class TradeResult:
    position: BacktestPosition
    exit_date: date
    exit_value: float
    pnl: float                  # entry_credit - exit_value
    pnl_pct: float              # pnl / max_risk
    exit_reason: str            # profit_target, stop_loss, dte_close, expiration
    max_adverse_excursion: float  # worst unrealized P&L during trade
    days_held: int
```

## Parameter Sweep

### Default Grid

```python
SWEEP_DEFAULTS = {
    "delta": [0.08, 0.10, 0.12, 0.15, 0.20, 0.25],
    "dte": [7, 14, 21, 30, 45],
    "profit_target": [0.25, 0.40, 0.50, 0.60, 0.75],
    "spread_width": [5, 10],
}
# 6 × 5 × 5 × 2 = 300 combinations per symbol
```

For each combination, the sweep:
1. Creates a `BacktestParams` with `use_adaptive=False` (static params for clean comparison)
2. Runs the full simulation
3. Computes metrics
4. Stores results

### Custom Grid

Configurable in `strategy.yaml`:
```yaml
backtest:
  sweep:
    delta: [0.10, 0.15, 0.20]
    dte: [14, 21, 30]
    profit_target: [0.40, 0.50, 0.60]
```

### Output

Results saved to `~/.nodeble/data/backtest/sweep_results.csv`:
```
symbol, delta, dte, profit_target, spread_width,
total_trades, win_rate, total_pnl, avg_win, avg_loss,
max_drawdown, sharpe_ratio
```

Sorted by Sharpe ratio. Top 10 printed to console.

## Feature Importance Analysis

### Dataset Construction

From completed trades, build a feature matrix:
- **Features (24):** 20 indicator votes at entry + VIX + VIX9D + term_ratio + bull_share
- **Target:** 1 (win: pnl > 0) or 0 (loss: pnl <= 0)

### Model

```python
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score

model = RandomForestClassifier(n_estimators=100, random_state=42)
cv_scores = cross_val_score(model, X, y, cv=5)
model.fit(X, y)
importances = dict(zip(feature_names, model.feature_importances_))
```

### Interpretation Guide

| Metric | What it means | Action |
|--------|--------------|--------|
| Importance > 0.05 | Strong predictor of IC win/loss | Keep, possibly upweight |
| Importance 0.02-0.05 | Moderate predictor | Keep as-is |
| Importance < 0.02 | Adds noise | Consider dropping |
| CV accuracy ~50% | Indicators don't predict IC outcomes | Strategy is VIX-driven, not indicator-driven |
| CV accuracy 60%+ | Indicators add real predictive value | Reweight voting engine accordingly |
| Volatility category dominates | Range-detection > direction-detection for IC | Validates our hypothesis |
| Volume category low | Volume indicators don't help IC | Drop or deprioritize |

### Output Report

Saved to `~/.nodeble/data/backtest/feature_importance.txt` and printed to console:

```
=== Indicator Feature Importance ===
Rank  Indicator            Importance  Category
1     atr_trend            0.142       volatility
2     bollinger_position   0.098       volatility
...
20    volume_sma_ratio     0.012       volume

Cross-validation accuracy: 0.68 (±0.03)

Category breakdown:
  volatility:  0.31 (5 indicators)
  trend:       0.24 (5 indicators)
  momentum:    0.23 (5 indicators)
  volume:      0.12 (5 indicators)
  market:      0.10 (VIX, VIX9D, term_ratio, bull_share)

Recommendations:
  DROP (importance < 0.02): volume_sma_ratio, cmf_20
  KEEP (importance > 0.05): atr_trend, bollinger_position, adx_trend, rsi_14
```

## Metrics

For each backtest run, compute:

| Metric | Formula |
|--------|---------|
| Total trades | count of completed trades |
| Win rate | wins / total_trades |
| Total P&L | sum of all trade P&L |
| Avg win | mean P&L of winning trades |
| Avg loss | mean P&L of losing trades |
| Max drawdown | largest peak-to-trough decline in cumulative P&L |
| Sharpe ratio | mean(daily_returns) / std(daily_returns) × √252 |

## CLI Interface

```
python -m nodeble --mode backtest [options]

Options:
  --sweep          Run parameter sweep (default grid or config-driven)
  --analyze        Run feature importance analysis after backtest
  --symbols SPY    Comma-separated symbols (default: SPY,QQQ,IWM)
  --years 5        Years of history (default: 5)
  --force-fetch    Re-download data even if cache exists
```

## Files

### New

| File | Purpose |
|------|---------|
| `src/nodeble/backtest/__init__.py` | Package init |
| `src/nodeble/backtest/data.py` | Fetch + cache OHLCV, VIX, VIX9D to Parquet |
| `src/nodeble/backtest/pricing.py` | Black-Scholes pricing, delta, strike finder |
| `src/nodeble/backtest/simulator.py` | Day-by-day IC simulation engine |
| `src/nodeble/backtest/sweep.py` | Parameter sweep grid search |
| `src/nodeble/backtest/analysis.py` | Random Forest feature importance + report |
| `src/nodeble/backtest/runner.py` | Orchestrator: data → simulate → sweep → analyze |
| `tests/test_pricing.py` | BS formula correctness tests |
| `tests/test_simulator.py` | Simulator logic tests (entry, exit, P&L) |

### Modified

| File | Change |
|------|--------|
| `src/nodeble/__main__.py` | Add `--mode backtest` with `--sweep`, `--analyze`, `--symbols`, `--years`, `--force-fetch` |
| `pyproject.toml` | Add `scikit-learn` and `scipy` dependencies |

## Dependencies

- `scikit-learn` — new (Random Forest for feature importance)
- `scipy` — new (for `norm.cdf` in Black-Scholes formula)
- `pandas`, `numpy`, `yfinance` — already present
