import pandas as pd
import numpy as np
from nodeble.backtest.simulator import (
    BacktestParams, BacktestPosition, TradeResult,
    simulate_ic, compute_metrics,
)


def _make_flat_ohlcv(start_price=500.0, days=300, daily_move=0.001):
    """Generate flat/slightly-moving OHLCV data."""
    dates = pd.bdate_range(start="2021-01-04", periods=days)
    np.random.seed(42)
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
    if results:
        wins = sum(1 for r in results if r.pnl > 0)
        assert wins / len(results) > 0.5


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
