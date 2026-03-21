# -*- coding: utf-8 -*-
"""Parameter sweep: grid search across IC parameter combinations."""
import csv
import itertools
import logging

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
    """Run parameter sweep for a single symbol."""
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
            call_delta=delta,
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
