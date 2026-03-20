from nodeble.strategy.manager import evaluate_positions, verify_pending_fills, cleanup_stale_orders
from nodeble.core.state import SpreadState


def test_evaluate_empty_state():
    state = SpreadState()
    cfg = {
        "management": {
            "profit_take_pct": 0.50,
            "stop_loss_pct": 2.0,
            "close_before_dte": 1,
        }
    }
    actions = evaluate_positions(state=state, broker=None, strategy_cfg=cfg)
    assert actions == []
