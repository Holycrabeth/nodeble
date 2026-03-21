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
    """All neutral votes -> HOLD (no_active_signal)."""
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
    """Only 4/20 active (20%) < 35% quorum -> HOLD."""
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
    """Active in only 2 categories < 3 required -> HOLD."""
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
    """bull_share ~0.50 within +/-0.06 deadband -> HOLD."""
    engine = VotingEngine()
    # 10 bull, 10 bear -> bull_share = 0.50 -> in deadband
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
    """bull_share >= 0.70 -> STRONG_BUY."""
    engine = VotingEngine()
    # 14 bull, 6 bear -> bull_share = 0.70
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
    """bear_share >= 0.58 -> SELL."""
    engine = VotingEngine()
    # 8 bull, 12 bear -> bear_share = 0.60
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
