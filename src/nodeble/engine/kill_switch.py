# -*- coding: utf-8 -*-
"""Kill switch order cancellation helper.

When a strategy's kill_switch is ON, cancel all pending orders
for that strategy's symbols at the broker.
"""

import logging

from nodeble.core.audit import log_event

logger = logging.getLogger(__name__)


def cancel_pending_orders(
    broker,
    notifier,
    symbols: list | set,
    sec_type: str,
    strategy_label: str,
) -> list[dict]:
    """Cancel all open orders matching the given symbols.

    Args:
        broker: BrokerAdapter instance (may be None in dry-run).
        notifier: TelegramNotifier instance (may be None).
        symbols: Set/list of underlying symbols to filter by.
        sec_type: "STK" or "OPT".
        strategy_label: For logging (e.g. "condor").

    Returns:
        List of dicts describing cancelled orders.
    """
    if broker is None:
        logger.info(f"Kill switch cancel: broker unavailable, skipping ({strategy_label})")
        return []

    symbol_set = set(s.upper() for s in symbols)

    try:
        open_orders = broker.get_open_orders(sec_type=sec_type)
    except Exception as e:
        msg = f"Kill switch: failed to get open orders for {strategy_label}: {e}"
        logger.error(msg)
        log_event(strategy_label, "kill_switch_cancel_error", error=str(e))
        if notifier:
            try:
                notifier.send(f"ALERT: {msg}")
            except Exception:
                pass
        return []

    matching = []
    for order in open_orders:
        order_symbol = getattr(order, "symbol", "")
        if order_symbol.upper() in symbol_set:
            matching.append(order)

    if not matching:
        logger.info(f"Kill switch ON ({strategy_label}) — no pending orders to cancel")
        log_event(strategy_label, "kill_switch_cancel", cancelled=0)
        return []

    cancelled = []
    for order in matching:
        order_id = getattr(order, "id", 0)
        order_symbol = getattr(order, "symbol", "?")
        try:
            broker.cancel_order(order_id)
            cancelled.append({
                "order_id": order_id,
                "symbol": order_symbol,
                "status": "cancelled",
            })
            logger.info(f"Kill switch cancel: {order_symbol} order_id={order_id}")
        except Exception as e:
            cancelled.append({
                "order_id": order_id,
                "symbol": order_symbol,
                "status": "error",
                "error": str(e),
            })
            logger.error(f"Kill switch cancel failed: {order_symbol} order_id={order_id}: {e}")

    ok_count = sum(1 for c in cancelled if c["status"] == "cancelled")
    err_count = sum(1 for c in cancelled if c["status"] == "error")
    log_event(
        strategy_label, "kill_switch_cancel",
        cancelled=ok_count, errors=err_count,
        orders=[c["symbol"] for c in cancelled],
    )

    symbols_str = ", ".join(c["symbol"] for c in cancelled if c["status"] == "cancelled")
    msg = f"Kill switch ON — cancelled {ok_count} pending orders: [{symbols_str}]"
    if err_count:
        msg += f" ({err_count} cancel errors)"
    logger.warning(msg)

    if notifier:
        try:
            notifier.send(f"{strategy_label.upper()}: {msg}")
        except Exception:
            pass

    return cancelled
