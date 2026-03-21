# -*- coding: utf-8 -*-
"""Feature importance analysis using Random Forest on backtest trade results."""
import logging

import numpy as np

from nodeble.backtest.simulator import TradeResult
from nodeble.paths import get_data_dir

logger = logging.getLogger(__name__)

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
    """Run Random Forest feature importance analysis on trade results."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import cross_val_score

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

        # Use established feature_names order, not current trade's keys
        row = [votes.get(name, 0) for name in feature_names[:-4]]
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

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    cv_folds = min(5, max(2, len(X_rows) // 10))
    cv_scores = cross_val_score(model, X, y, cv=cv_folds)

    model.fit(X, y)
    importances = dict(zip(feature_names, model.feature_importances_))

    sorted_imp = sorted(importances.items(), key=lambda x: x[1], reverse=True)

    cat_totals = {}
    for name, imp in importances.items():
        cat = INDICATOR_CATEGORIES.get(name, "market")
        cat_totals[cat] = cat_totals.get(cat, 0.0) + imp

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

    lines = []
    lines.append(f"{'='*60}")
    lines.append(f"  INDICATOR FEATURE IMPORTANCE")
    lines.append(f"{'='*60}")
    lines.append(f"{'Rank':<5} {'Indicator':<25} {'Importance':<12} {'Category':<12}")
    lines.append("-" * 60)

    for i, (name, imp) in enumerate(analysis["importances"], 1):
        cat = INDICATOR_CATEGORIES.get(name, "market")
        lines.append(f"{i:<5} {name:<25} {imp:<12.4f} {cat:<12}")

    lines.append(f"\nCV accuracy: {analysis['cv_accuracy']:.2f} (+/- {analysis['cv_std']:.2f})")
    lines.append(f"Total trades: {analysis['total_trades']}")

    if analysis["keep"]:
        lines.append(f"\nKEEP: {', '.join(analysis['keep'])}")
    if analysis["drop"]:
        lines.append(f"DROP: {', '.join(analysis['drop'])}")

    path.write_text("\n".join(lines))
    logger.info(f"Feature importance report saved to {path}")
