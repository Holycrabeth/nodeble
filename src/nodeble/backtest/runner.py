# -*- coding: utf-8 -*-
"""Backtest orchestrator: data loading -> simulation -> sweep -> analysis."""
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
    print(f"\nLoading {years} years of data for {', '.join(symbols)}...")
    data = load_backtest_data(symbols, years=years, force_fetch=force_fetch)

    if not data.ohlcv:
        print("ERROR: No data loaded. Check symbols and network connection.")
        return

    # Parameter sweep
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

    # Single run (with optional analysis)
    adaptive_cfg = strategy_cfg.get("adaptive", {}) if strategy_cfg else None
    params = BacktestParams(use_adaptive=bool(adaptive_cfg), use_indicators=True)

    if strategy_cfg:
        sel = strategy_cfg.get("selection", {})
        mgmt = strategy_cfg.get("management", {})
        params.put_delta = sel.get("put_delta_max", params.put_delta)
        params.call_delta = sel.get("call_delta_max", params.call_delta)
        params.dte = sel.get("dte_ideal", sel.get("dte_max", params.dte))
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

    # Feature importance
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
