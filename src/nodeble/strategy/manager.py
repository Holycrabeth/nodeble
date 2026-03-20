# -*- coding: utf-8 -*-
"""Options spread position manager: verify fills, profit/stop/DTE management, close spreads."""

import logging
import math
from datetime import date

from nodeble.core.state import SpreadState, SpreadPosition
from nodeble.core import risk as options_risk
from nodeble.core.audit import log_event

logger = logging.getLogger(__name__)


class SpreadAction:
    """Describes an action to take on a spread position."""

    def __init__(self, position: SpreadPosition, action: str, reason: str,
                 current_value: float = 0.0):
        self.position = position
        self.action = action  # close_profit, close_stop, close_dte, expire
        self.reason = reason
        self.current_value = current_value


def cleanup_stale_orders(broker, state: SpreadState, dry_run: bool = False) -> list[int]:
    """Cancel unfilled spread leg orders from previous days.

    SCOPED: Only cancels orders tracked in spread state (not theta orders).
    """
    cancelled = []

    # Collect all pending order IDs from spread state
    spread_order_ids = set()
    for pos in state.positions.values():
        for leg in pos.legs:
            if leg.status == "pending" and leg.order_id > 0:
                spread_order_ids.add(leg.order_id)

    if not spread_order_ids:
        return cancelled

    try:
        open_orders = broker.get_open_orders(sec_type="OPT")
    except Exception as e:
        logger.error(f"Failed to get open option orders: {e}")
        return cancelled

    for order in (open_orders or []):
        order_id = getattr(order, "id", None)
        if order_id is None or order_id not in spread_order_ids:
            continue
        if dry_run:
            logger.info(f"DRY RUN: Would cancel stale spread order {order_id}")
            cancelled.append(order_id)
        else:
            try:
                broker.cancel_order(order_id)
                logger.info(f"Cancelled stale spread order {order_id}")
                cancelled.append(order_id)
            except Exception as e:
                logger.warning(f"Failed to cancel order {order_id}: {e}")

    if cancelled:
        logger.info(f"Cleaned up {len(cancelled)} stale spread orders")
    return cancelled


def verify_pending_fills(broker, state: SpreadState) -> dict:
    """Verify fill status of pending legs.

    Returns summary: {confirmed: N, removed: N, partial: N}
    """
    result = {"confirmed": 0, "removed": 0, "partial": 0}

    for pos in list(state.positions.values()):
        if pos.status not in ("pending", "partial"):
            continue

        all_filled = True
        any_filled = False
        any_cancelled = False

        for leg in pos.legs:
            if leg.status != "pending" or leg.order_id == 0:
                if leg.status == "filled":
                    any_filled = True
                continue

            try:
                order = broker.get_order(leg.order_id)
                raw_status = getattr(order, "status", "")
                status = raw_status.name if hasattr(raw_status, "name") else str(raw_status).upper()
                if status == "FILLED":
                    leg.status = "filled"
                    any_filled = True
                    logger.info(f"Leg filled: {leg.identifier} order={leg.order_id}")
                elif status in ("CANCELLED", "EXPIRED", "REJECTED"):
                    leg.status = "cancelled"
                    any_cancelled = True
                    logger.info(f"Leg {status}: {leg.identifier} order={leg.order_id}")
                else:
                    all_filled = False
            except Exception as e:
                logger.warning(f"Failed to check order {leg.order_id}: {e}")
                all_filled = False

        # Determine position state
        filled_legs = [l for l in pos.legs if l.status == "filled"]
        pending_legs = [l for l in pos.legs if l.status == "pending"]
        cancelled_legs = [l for l in pos.legs if l.status == "cancelled"]

        if all_filled and len(filled_legs) == len(pos.legs):
            # All legs filled — transition to open
            pos.status = "open"
            # Calculate entry credit
            credit = sum(l.entry_premium for l in pos.legs if l.action == "SELL")
            debit = sum(l.entry_premium for l in pos.legs if l.action == "BUY")
            pos.entry_credit = credit - debit
            if not pos.credit_counted:
                state.total_credit_collected += pos.entry_credit * pos.contracts * 100
                pos.credit_counted = True
            result["confirmed"] += 1
            logger.info(f"Position confirmed open: {pos.spread_id}")

        elif any_cancelled and not pending_legs:
            if any_filled:
                # Partial fill — needs cleanup
                pos.status = "partial"
                result["partial"] += 1
                logger.warning(f"Partial position: {pos.spread_id}")
            else:
                # All cancelled — remove phantom
                del state.positions[pos.spread_id]
                result["removed"] += 1
                logger.info(f"Removed phantom position: {pos.spread_id}")

    return result


def evaluate_positions(
    state: SpreadState,
    broker,
    strategy_cfg: dict,
) -> list[SpreadAction]:
    """Evaluate all open positions for profit/stop/DTE conditions.

    Returns list of SpreadAction objects.
    """
    mgmt = strategy_cfg.get("management", {})
    profit_target_pct = mgmt.get("profit_take_pct", 0.50)
    stop_loss_pct = mgmt.get("stop_loss_pct", 2.0)
    close_before_dte = mgmt.get("close_before_dte") or mgmt.get("close_dte_threshold", 1)

    actions = []
    open_positions = state.get_open_positions()

    if not open_positions:
        logger.info("No open spread positions to manage")
        return actions

    # Gather quotes for all legs
    all_identifiers = []
    for pos in open_positions:
        for leg in pos.legs:
            if leg.status == "filled":
                all_identifiers.append(leg.identifier)

    if not all_identifiers:
        return actions

    try:
        briefs = broker.get_option_briefs(all_identifiers)
    except Exception as e:
        logger.error(f"Failed to get option briefs: {e}")
        return actions

    quote_map = {}
    for b in (briefs or []):
        ident = getattr(b, "identifier", "")
        bid = float(getattr(b, "bid_price", 0) or 0)
        ask = float(getattr(b, "ask_price", 0) or 0)
        # NaN from broker means quote unavailable — treat as 0
        if math.isnan(bid):
            bid = 0.0
            log_event("spreads", "nan_quote", identifier=ident, field="bid")
        if math.isnan(ask):
            ask = 0.0
            log_event("spreads", "nan_quote", identifier=ident, field="ask")
        quote_map[ident] = {"bid": bid, "ask": ask}

    today = date.today()

    for pos in open_positions:
        # Naked leg safety check every manage cycle
        if not options_risk.verify_no_naked_legs(pos):
            logger.error(
                f"NAKED LEG in {pos.spread_id} — flagging for immediate close"
            )
            actions.append(SpreadAction(
                position=pos,
                action="close_stop",
                reason="NAKED LEG DETECTED — emergency close",
            ))
            continue

        # Compute current cost to close
        # Buy back short legs at ask, sell long legs at bid
        close_cost = 0.0
        all_quotes_available = True

        for leg in pos.legs:
            if leg.status != "filled":
                continue
            quote = quote_map.get(leg.identifier)
            if quote is None or (quote["bid"] == 0 and quote["ask"] == 0):
                all_quotes_available = False
                break
            if leg.action == "SELL":
                close_cost += quote["ask"]  # buy back
            elif leg.action == "BUY":
                close_cost -= quote["bid"]  # sell

        if not all_quotes_available:
            # Market likely closed — skip evaluation
            pos.nan_quote_streak = getattr(pos, "nan_quote_streak", 0) + 1
            dte = _compute_dte(pos.expiry, today)
            pos.current_dte = dte
            if dte <= 0:
                actions.append(SpreadAction(
                    position=pos, action="expire",
                    reason=f"Option expired (exp={pos.expiry})",
                ))
            continue

        pos.nan_quote_streak = 0
        pos.current_value = close_cost
        dte = _compute_dte(pos.expiry, today)
        pos.current_dte = dte

        # Profit target: close_cost < entry_credit * profit_target_pct
        if pos.entry_credit > 0 and close_cost <= pos.entry_credit * profit_target_pct:
            actions.append(SpreadAction(
                position=pos,
                action="close_profit",
                reason=(
                    f"Profit target: value ${close_cost:.2f} <= "
                    f"${pos.entry_credit * profit_target_pct:.2f} "
                    f"({profit_target_pct:.0%} of ${pos.entry_credit:.2f})"
                ),
                current_value=close_cost,
            ))
            continue

        # Stop loss: close_cost > entry_credit * stop_loss_pct
        if pos.entry_credit > 0 and close_cost >= pos.entry_credit * stop_loss_pct:
            actions.append(SpreadAction(
                position=pos,
                action="close_stop",
                reason=(
                    f"Stop loss: value ${close_cost:.2f} >= "
                    f"${pos.entry_credit * stop_loss_pct:.2f} "
                    f"({stop_loss_pct:.0%} of ${pos.entry_credit:.2f})"
                ),
                current_value=close_cost,
            ))
            continue

        # DTE close
        if dte <= close_before_dte:
            actions.append(SpreadAction(
                position=pos,
                action="close_dte",
                reason=f"DTE close: {dte} <= {close_before_dte}",
                current_value=close_cost,
            ))
            continue

        logger.info(
            f"{pos.spread_id}: holding (value=${close_cost:.2f}, "
            f"credit=${pos.entry_credit:.2f}, DTE={dte})"
        )

    return actions


def _compute_dte(expiry: str, ref_date: date | None = None) -> int:
    if ref_date is None:
        ref_date = date.today()
    try:
        exp_date = date.fromisoformat(expiry[:10])
        return (exp_date - ref_date).days
    except ValueError:
        return 0
