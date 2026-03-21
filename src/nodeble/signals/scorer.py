# -*- coding: utf-8 -*-
"""Voting engine: collect indicator votes, apply quorum/deadband, produce decision."""

import logging
from dataclasses import dataclass, field

import yaml
import pandas as pd

from nodeble.signals.base import BaseIndicator

logger = logging.getLogger(__name__)

# Valid decisions
DECISIONS = ("STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL")


@dataclass
class VoteResult:
    """Result of voting on a single symbol."""

    symbol: str
    decision: str  # STRONG_BUY / BUY / HOLD / SELL / STRONG_SELL
    reason: str
    confidence: float  # 0.0 to 1.0
    bull_count: int
    bear_count: int
    neutral_count: int
    active_count: int
    active_ratio: float
    bull_share: float
    bear_share: float
    active_categories: int
    votes: dict = field(default_factory=dict)  # indicator_name -> vote


def load_voting_config(path: str = "config/voting.yaml") -> dict:
    """Load voting parameters from config file with fallback defaults."""
    defaults = {
        "implemented_indicators": 20,
        "min_active_ratio": 0.35,
        "min_active_categories": 3,
        "deadband": 0.06,
        "buy_threshold": 0.58,
        "strong_buy_threshold": 0.70,
        "sell_threshold": 0.58,
        "strong_sell_threshold": 0.70,
    }
    try:
        with open(path, "r") as f:
            raw = yaml.safe_load(f)
        voting = raw.get("voting", {})
        for key in defaults:
            if key in voting:
                defaults[key] = voting[key]
    except FileNotFoundError:
        logger.warning(f"Voting config not found: {path}, using defaults")
    return defaults


class VotingEngine:
    """Collect indicator votes and produce a trading decision."""

    def __init__(self, config: dict = None):
        if config is not None:
            self.cfg = {
                "implemented_indicators": 20,
                "min_active_ratio": 0.35,
                "min_active_categories": 3,
                "deadband": 0.06,
                "buy_threshold": 0.58,
                "strong_buy_threshold": 0.70,
                "sell_threshold": 0.58,
                "strong_sell_threshold": 0.70,
            }
            self.cfg.update(config)
        else:
            self.cfg = load_voting_config()

    def score(
        self, symbol: str, df: pd.DataFrame, indicators: list[BaseIndicator]
    ) -> VoteResult:
        """Run all indicators on df, apply quorum + deadband, return decision."""

        # Set symbol in df.attrs for sentiment indicators
        df.attrs['symbol'] = symbol

        # Collect votes
        votes = {}
        for ind in indicators:
            try:
                vote = ind.compute(df)
                if vote not in (-1, 0, 1):
                    logger.warning(f"{ind.name} returned invalid vote {vote}, treating as 0")
                    vote = 0
            except Exception as e:
                logger.error(f"{ind.name} failed on {symbol}: {e}")
                vote = 0
            votes[ind.name] = vote

        bull = sum(1 for v in votes.values() if v == 1)
        bear = sum(1 for v in votes.values() if v == -1)
        neutral = sum(1 for v in votes.values() if v == 0)
        active = bull + bear
        impl = self.cfg["implemented_indicators"]
        active_ratio = active / impl if impl > 0 else 0.0

        # Category diversity: count categories with at least one non-neutral vote
        category_votes = {}
        for ind in indicators:
            v = votes[ind.name]
            if v != 0:
                category_votes[ind.category] = True
        active_categories = len(category_votes)

        # Default result values
        bull_share = 0.0
        bear_share = 0.0
        confidence = 0.0

        # Gate 1: no active signals
        if active == 0:
            return self._result(
                symbol, "HOLD", "no_active_signal", 0.0,
                bull, bear, neutral, active, active_ratio,
                bull_share, bear_share, active_categories, votes,
            )

        # Gate 2: quorum not met
        if active_ratio < self.cfg["min_active_ratio"]:
            return self._result(
                symbol, "HOLD", "below_quorum", 0.0,
                bull, bear, neutral, active, active_ratio,
                bull_share, bear_share, active_categories, votes,
            )

        # Gate 3: category diversity
        if active_categories < self.cfg["min_active_categories"]:
            return self._result(
                symbol, "HOLD", "insufficient_category_diversity", 0.0,
                bull, bear, neutral, active, active_ratio,
                bull_share, bear_share, active_categories, votes,
            )

        # Compute shares and confidence
        bull_share = bull / active
        bear_share = bear / active
        confidence = abs(bull_share - 0.5) * 2

        # Gate 4: deadband
        if abs(bull_share - 0.5) <= self.cfg["deadband"]:
            return self._result(
                symbol, "HOLD", "in_deadband", confidence,
                bull, bear, neutral, active, active_ratio,
                bull_share, bear_share, active_categories, votes,
            )

        # Decision thresholds (checked in order: strongest first)
        if bull_share >= self.cfg["strong_buy_threshold"]:
            decision, reason = "STRONG_BUY", "bull_consensus"
        elif bull_share >= self.cfg["buy_threshold"]:
            decision, reason = "BUY", "bull_bias"
        elif bear_share >= self.cfg["strong_sell_threshold"]:
            decision, reason = "STRONG_SELL", "bear_consensus"
        elif bear_share >= self.cfg["sell_threshold"]:
            decision, reason = "SELL", "bear_bias"
        else:
            # In buffer zone between deadband and threshold
            decision, reason = "HOLD", "weak_edge"

        return self._result(
            symbol, decision, reason, confidence,
            bull, bear, neutral, active, active_ratio,
            bull_share, bear_share, active_categories, votes,
        )

    def _result(
        self, symbol, decision, reason, confidence,
        bull, bear, neutral, active, active_ratio,
        bull_share, bear_share, active_categories, votes,
    ) -> VoteResult:
        return VoteResult(
            symbol=symbol,
            decision=decision,
            reason=reason,
            confidence=confidence,
            bull_count=bull,
            bear_count=bear,
            neutral_count=neutral,
            active_count=active,
            active_ratio=round(active_ratio, 4),
            bull_share=round(bull_share, 4),
            bear_share=round(bear_share, 4),
            active_categories=active_categories,
            votes=votes,
        )
