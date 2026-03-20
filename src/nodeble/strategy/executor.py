# -*- coding: utf-8 -*-
"""Sequential leg execution with fill confirmation and rollback.

SAFETY CRITICAL:
- Long (protective) leg FIRST, short leg SECOND when opening.
- Short leg FIRST (buy back), long leg SECOND when closing.
- State saved after every leg placement.
- verify_no_naked_legs() before every short order.
"""

import logging
import math
import time
from datetime import date

from nodeble.core.state import SpreadState, SpreadPosition, SpreadLeg
from nodeble.strategy.strike_selector import SpreadCandidate
from nodeble.core import risk as options_risk
from nodeble.core.audit import log_event

logger = logging.getLogger(__name__)


class SpreadExecutor:
    """Execute credit spreads with sequential leg placement and rollback."""

    def __init__(self, broker, notifier, config: dict, state: SpreadState, state_path: str):
        self.broker = broker
        self.notifier = notifier
        self.config = config
        self.state = state
        self.state_path = state_path

        exec_cfg = config.get("execution", {})
        self.fill_timeout = exec_cfg.get("fill_timeout_sec", 30)
        self.max_slippage = exec_cfg.get("max_leg_slippage", 0.10)
        self.retry_attempts = exec_cfg.get("retry_attempts", 2)
        self.poll_interval = 3  # seconds between fill checks

    def _save_state(self):
        """Save state after every leg — crash safety."""
        self.state.save(self.state_path)

    def _notify(self, message: str):
        if self.notifier:
            try:
                self.notifier.send(message)
            except Exception as e:
                logger.warning(f"Notification failed: {e}")

    def _poll_for_fill(self, order_id: int, timeout: int) -> str:
        """Poll broker for order fill status.

        Returns: "FILLED", "CANCELLED", "EXPIRED", "REJECTED", "TIMEOUT"
        """
        start = time.time()
        while time.time() - start < timeout:
            try:
                order = self.broker.get_order(order_id)
                raw_status = getattr(order, "status", "")
                status = raw_status.name if hasattr(raw_status, "name") else str(raw_status).upper()
                if status == "FILLED":
                    return "FILLED"
                if status in ("CANCELLED", "EXPIRED", "REJECTED"):
                    return status
                # Still pending (NEW, PARTIALLY_FILLED, etc.)
            except Exception as e:
                logger.warning(f"Poll error for order {order_id}: {e}")
            time.sleep(self.poll_interval)
        return "TIMEOUT"

    def _cancel_order(self, order_id: int) -> bool:
        """Cancel an order. Returns True if successful."""
        try:
            self.broker.cancel_order(order_id)
            logger.info(f"Cancelled order {order_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    def _emergency_close_leg(self, leg: SpreadLeg, position: SpreadPosition = None) -> bool:
        """Emergency close a filled leg using market order.

        Saves order_id to a new emergency leg in position state for cleanup tracking.
        Returns True if close order placed.
        """
        try:
            close_action = "SELL" if leg.action == "BUY" else "BUY"

            order_id = self.broker.place_option_market_order(
                identifier=leg.identifier,
                action=close_action,
                quantity=leg.contracts,
            )

            # Mark original leg so close_spread won't double-process it
            leg.status = "closing"

            # Track emergency close order_id in state for cleanup
            if position is not None:
                emergency_leg = SpreadLeg(
                    identifier=leg.identifier,
                    strike=leg.strike,
                    put_call=leg.put_call,
                    action=close_action,
                    contracts=leg.contracts,
                    entry_premium=0.0,
                    order_id=order_id,
                    status="pending",
                )
                position.legs.append(emergency_leg)
                self._save_state()

            logger.warning(
                f"EMERGENCY CLOSE: {close_action} {leg.contracts} {leg.identifier} "
                f"MARKET | order_id={order_id}"
            )
            self._notify(
                f"EMERGENCY CLOSE: {close_action} {leg.identifier} MARKET"
            )
            return True
        except Exception as e:
            logger.error(f"EMERGENCY CLOSE FAILED for {leg.identifier}: {e}")
            self._notify(
                f"ALERT: Emergency close FAILED for {leg.identifier} — MANUAL INTERVENTION NEEDED"
            )
            return False

    def _check_price_guard(self, candidate: SpreadCandidate) -> str | None:
        """Check if underlying price moved too much since scan.

        Returns None if OK, or an abort reason string.
        """
        if candidate.scan_price <= 0:
            return None  # no scan price recorded — skip guard (backward compat)

        try:
            current_price = self.broker.get_stock_price(candidate.underlying)
        except Exception as e:
            reason = f"PRICE GUARD: failed to get price for {candidate.underlying}: {e}. Aborting (fail-closed)."
            logger.warning(reason)
            self._notify(reason)
            return reason

        if current_price <= 0:
            reason = f"PRICE GUARD: got invalid price ({current_price}) for {candidate.underlying}. Aborting (fail-closed)."
            logger.warning(reason)
            return reason

        move_pct = abs(current_price - candidate.scan_price) / candidate.scan_price
        threshold = self.config.get("selection", {}).get("price_guard_pct", 0.03)

        if move_pct > threshold:
            reason = (
                f"PRICE GUARD: {candidate.underlying} moved {move_pct:.1%} "
                f"(scan={candidate.scan_price:.2f} -> now={current_price:.2f}), "
                f"threshold={threshold:.0%}. Aborting spread."
            )
            logger.warning(reason)
            self._notify(reason)
            return reason

        return None

    def _check_delta_guard(self, candidate: SpreadCandidate) -> str | None:
        """Check if short leg delta has blown up since scan.

        For iron condors, checks both short put and short call.
        Returns None if OK, or an abort reason string.
        """
        sel = self.config.get("selection", {})
        # Use the configured max delta; fall back to delta_range upper bound
        delta_range = sel.get("delta_range", [0.15, 0.30])
        max_delta = sel.get("max_delta", delta_range[1] if isinstance(delta_range, list) else 0.30)

        # Collect short leg identifiers to check
        short_ids = []
        if candidate.spread_type in ("bull_put", "iron_condor") and candidate.short_put_identifier:
            short_ids.append(("short_put", candidate.short_put_identifier))
        if candidate.spread_type in ("bear_call", "iron_condor") and candidate.short_call_identifier:
            short_ids.append(("short_call", candidate.short_call_identifier))

        if not short_ids:
            return None

        identifiers = [sid for _, sid in short_ids]
        try:
            briefs = self.broker.get_option_briefs(identifiers)
        except Exception as e:
            reason = f"DELTA GUARD: failed to get briefs for {candidate.underlying}: {e}. Aborting (fail-closed)."
            logger.warning(reason)
            self._notify(reason)
            return reason

        if not briefs:
            reason = f"DELTA GUARD: got empty briefs for {candidate.underlying}. Aborting (fail-closed)."
            logger.warning(reason)
            return reason

        brief_map = {}
        for b in briefs:
            ident = getattr(b, "identifier", "")
            brief_map[ident] = b

        for label, ident in short_ids:
            brief = brief_map.get(ident)
            if brief is None:
                continue
            current_delta = abs(float(getattr(brief, "delta", 0) or 0))
            if current_delta > max_delta:
                reason = (
                    f"DELTA GUARD: {candidate.underlying} {label} delta={current_delta:.2f} "
                    f"> max={max_delta:.2f}. Aborting spread."
                )
                logger.warning(reason)
                self._notify(reason)
                return reason

        return None

    def execute_spread(
        self,
        candidate: SpreadCandidate,
        dry_run: bool = False,
    ) -> dict:
        """Execute a vertical spread (bull_put or bear_call).

        Returns result dict with status.
        """
        today_str = date.today().isoformat()

        # Build spread ID
        if candidate.spread_type == "bull_put":
            short_strike = candidate.short_put_strike
            long_strike = candidate.long_put_strike
        else:  # bear_call
            short_strike = candidate.short_call_strike
            long_strike = candidate.long_call_strike

        spread_id = (
            f"{candidate.underlying}_{candidate.spread_type}_{candidate.expiry}_"
            f"{short_strike:.0f}_{long_strike:.0f}"
        )

        result = {
            "spread_id": spread_id,
            "underlying": candidate.underlying,
            "spread_type": candidate.spread_type,
            "expiry": candidate.expiry,
            "expected_credit": candidate.total_credit,
            "contracts": candidate.contracts,
            "status": "unknown",
        }

        # Price guard: abort if underlying moved too much since scan
        if not dry_run:
            abort_reason = self._check_price_guard(candidate)
            if abort_reason:
                result["status"] = "aborted_price_guard"
                result["reason"] = abort_reason
                return result

        # Delta guard: abort if short leg delta exceeded max
        if not dry_run:
            abort_reason = self._check_delta_guard(candidate)
            if abort_reason:
                result["status"] = "aborted_delta_guard"
                result["reason"] = abort_reason
                return result

        if dry_run:
            result["status"] = "dry_run"
            logger.info(
                f"DRY RUN: Would open {candidate.spread_type} on {candidate.underlying} "
                f"exp={candidate.expiry} credit=${candidate.total_credit:.2f} "
                f"x{candidate.contracts}"
            )
            return result

        # Create position in state
        position = SpreadPosition(
            spread_id=spread_id,
            underlying=candidate.underlying,
            expiry=candidate.expiry,
            spread_type=candidate.spread_type,
            entry_date=today_str,
            contracts=candidate.contracts,
            status="pending",
        )

        # Determine legs based on spread type
        if candidate.spread_type == "bull_put":
            long_id = candidate.long_put_identifier
            long_strike_val = candidate.long_put_strike
            long_pc = "P"
            long_price = round(candidate.long_put_ask, 2)
            long_delta = candidate.long_put_delta
            short_id = candidate.short_put_identifier
            short_strike_val = candidate.short_put_strike
            short_pc = "P"
            short_price = round(candidate.short_put_bid, 2)
            short_delta = candidate.short_put_delta
        else:  # bear_call
            long_id = candidate.long_call_identifier
            long_strike_val = candidate.long_call_strike
            long_pc = "C"
            long_price = round(candidate.long_call_ask, 2)
            long_delta = candidate.long_call_delta
            short_id = candidate.short_call_identifier
            short_strike_val = candidate.short_call_strike
            short_pc = "C"
            short_price = round(candidate.short_call_bid, 2)
            short_delta = candidate.short_call_delta

        # Step 1: BUY long (protective) leg
        long_leg = SpreadLeg(
            identifier=long_id,
            strike=long_strike_val,
            put_call=long_pc,
            action="BUY",
            contracts=candidate.contracts,
            entry_premium=long_price,
            status="pending",
            entry_delta=long_delta,
        )
        position.legs.append(long_leg)
        self.state.positions[spread_id] = position
        self._save_state()

        try:
            order_id = self.broker.place_option_market_order(
                identifier=long_id,
                action="BUY",
                quantity=candidate.contracts,
            )
            long_leg.order_id = order_id
            self._save_state()
            logger.info(
                f"Long leg placed: BUY {candidate.contracts} {long_id} "
                f"MARKET (ref ${long_price:.2f}) | order_id={order_id}"
            )
        except Exception as e:
            logger.error(f"Long leg order failed: {e}")
            long_leg.status = "error"
            position.status = "error"
            self._save_state()
            result["status"] = "error_long_leg"
            result["error"] = str(e)
            return result

        # Step 2: Poll for long leg fill
        fill_status = self._poll_for_fill(order_id, self.fill_timeout)
        if fill_status != "FILLED":
            logger.warning(f"Long leg not filled ({fill_status}), cancelling")
            self._cancel_order(order_id)
            long_leg.status = "cancelled"
            position.status = "error"
            self._save_state()
            result["status"] = f"error_long_not_filled_{fill_status.lower()}"
            return result

        long_leg.status = "filled"
        self._save_state()
        logger.info(f"Long leg FILLED: {long_id}")

        # Refresh short leg bid from live briefs (scan price may be stale)
        try:
            briefs = self.broker.get_option_briefs([short_id])
            if briefs:
                fresh_bid = float(getattr(briefs[0], "bid_price", 0) or 0)
                if fresh_bid > 0:
                    old_price = short_price
                    short_price = round(fresh_bid, 2)
                    if old_price != short_price:
                        logger.info(
                            f"Short leg bid refreshed: {old_price} -> {short_price}"
                        )
        except Exception as e:
            logger.warning(f"Failed to refresh short bid, using scan price: {e}")

        # Step 3: SELL short leg (after verifying no naked exposure)
        short_leg = SpreadLeg(
            identifier=short_id,
            strike=short_strike_val,
            put_call=short_pc,
            action="SELL",
            contracts=candidate.contracts,
            entry_premium=short_price,
            status="pending",
            entry_delta=short_delta,
        )
        position.legs.append(short_leg)

        # CRITICAL: verify no naked legs before placing short
        # State is NOT saved until verification passes — a crash here
        # leaves state without the unverified short leg.
        if not options_risk.verify_no_naked_legs(position):
            logger.error("NAKED LEG CHECK FAILED — aborting short leg")
            short_leg.status = "error"
            position.status = "error"
            self._save_state()
            # Emergency close long leg
            self._emergency_close_leg(long_leg, position)
            result["status"] = "error_naked_check"
            return result

        self._save_state()

        try:
            order_id = self.broker.place_option_market_order(
                identifier=short_id,
                action="SELL",
                quantity=candidate.contracts,
            )
            short_leg.order_id = order_id
            self._save_state()
            logger.info(
                f"Short leg placed: SELL {candidate.contracts} {short_id} "
                f"MARKET (ref ${short_price:.2f}) | order_id={order_id}"
            )
        except Exception as e:
            logger.error(f"Short leg order failed: {e}")
            short_leg.status = "error"
            position.status = "error"
            self._save_state()
            # Rollback: close long leg
            self._emergency_close_leg(long_leg, position)
            result["status"] = "error_short_leg"
            result["error"] = str(e)
            return result

        # Step 4: Poll for short leg fill
        fill_status = self._poll_for_fill(order_id, self.fill_timeout)
        if fill_status != "FILLED":
            logger.warning(f"Short leg not filled ({fill_status}), rolling back")
            self._cancel_order(order_id)
            short_leg.status = "cancelled"
            position.status = "error"
            self._save_state()
            # Rollback: close long leg
            self._emergency_close_leg(long_leg, position)
            result["status"] = f"rolled_back_{fill_status.lower()}"
            return result

        short_leg.status = "filled"

        # Step 5: Compute net credit and finalize
        net_credit = short_price - long_price
        position.entry_credit = net_credit
        position.max_risk = candidate.spread_width - net_credit
        position.status = "open"
        if not position.credit_counted:
            self.state.total_credit_collected += net_credit * candidate.contracts * 100
            position.credit_counted = True
        self._save_state()

        # Check slippage
        slippage = candidate.total_credit - net_credit
        if slippage > self.max_slippage:
            logger.warning(
                f"Slippage warning: expected ${candidate.total_credit:.2f} "
                f"got ${net_credit:.2f} (slip=${slippage:.2f})"
            )

        result["status"] = "open"
        result["net_credit"] = net_credit
        result["long_order_id"] = long_leg.order_id
        result["short_order_id"] = short_leg.order_id

        logger.info(
            f"SPREAD OPEN: {spread_id} credit=${net_credit:.2f} "
            f"x{candidate.contracts} max_risk=${position.max_risk:.2f}"
        )

        return result

    def execute_iron_condor(
        self,
        candidate: SpreadCandidate,
        dry_run: bool = False,
        allow_degradation: bool = False,
    ) -> dict:
        """Execute an iron condor (put spread + call spread).

        Executes put side first, then call side.
        If call side fails and allow_degradation=True, put side remains as bull_put.
        If call side fails and allow_degradation=False, put side is closed (no directional exposure).
        """
        today_str = date.today().isoformat()
        spread_id = (
            f"{candidate.underlying}_iron_condor_{candidate.expiry}_"
            f"{candidate.short_put_strike:.0f}_{candidate.long_put_strike:.0f}_"
            f"{candidate.short_call_strike:.0f}_{candidate.long_call_strike:.0f}"
        )

        result = {
            "spread_id": spread_id,
            "underlying": candidate.underlying,
            "spread_type": "iron_condor",
            "expiry": candidate.expiry,
            "expected_credit": candidate.total_credit,
            "contracts": candidate.contracts,
            "status": "unknown",
        }

        # Price guard: abort if underlying moved too much since scan
        if not dry_run:
            abort_reason = self._check_price_guard(candidate)
            if abort_reason:
                result["status"] = "aborted_price_guard"
                result["reason"] = abort_reason
                return result

        # Delta guard: abort if short leg delta exceeded max
        if not dry_run:
            abort_reason = self._check_delta_guard(candidate)
            if abort_reason:
                result["status"] = "aborted_delta_guard"
                result["reason"] = abort_reason
                return result

        if dry_run:
            result["status"] = "dry_run"
            logger.info(
                f"DRY RUN: Would open iron_condor on {candidate.underlying} "
                f"exp={candidate.expiry} credit=${candidate.total_credit:.2f}"
            )
            return result

        position = SpreadPosition(
            spread_id=spread_id,
            underlying=candidate.underlying,
            expiry=candidate.expiry,
            spread_type="iron_condor",
            entry_date=today_str,
            contracts=candidate.contracts,
            status="pending",
        )
        self.state.positions[spread_id] = position

        # --- PUT SIDE (long put first, then short put) ---
        put_success = self._execute_side(
            position, candidate, "put", dry_run=False,
        )

        if not put_success:
            position.status = "error"
            self._save_state()
            result["status"] = "error_put_side"
            return result

        # --- CALL SIDE (long call first, then short call) ---
        call_success = self._execute_side(
            position, candidate, "call", dry_run=False,
        )

        if not call_success:
            if allow_degradation:
                # Degrade to bull_put — put side remains open
                position.spread_type = "bull_put"
                position.entry_credit = candidate.put_credit
                position.max_risk = candidate.spread_width - candidate.put_credit
                position.status = "open"
                self._save_state()
                logger.warning(
                    f"Iron condor degraded to bull_put for {candidate.underlying}"
                )
                result["status"] = "degraded_to_bull_put"
                result["net_credit"] = candidate.put_credit
                return result
            else:
                # No degradation allowed: close put side to avoid directional exposure
                logger.warning(
                    f"Iron condor call side failed for {candidate.underlying} — "
                    f"closing put side (degradation not allowed)"
                )
                position.spread_type = "bull_put"
                position.entry_credit = candidate.put_credit
                position.max_risk = candidate.spread_width - candidate.put_credit
                position.status = "open"
                self._save_state()

                close_result = self.close_spread(position)
                if close_result["status"] == "closed":
                    result["status"] = "error_call_side_aborted"
                    logger.info(
                        f"Put side closed after condor abort: "
                        f"P&L=${close_result.get('realized_pnl', 0):.2f}"
                    )
                else:
                    # Close failed — stays "open", manage cycle will retry
                    result["status"] = "error_call_side_close_pending"
                    self._notify(
                        f"ALERT: Iron condor aborted for {candidate.underlying} — "
                        f"put side close failed ({close_result['status']}), "
                        f"manage cycle will retry"
                    )
                return result

        # Both sides filled — full iron condor
        total_credit = 0.0
        for leg in position.legs:
            if leg.action == "SELL" and leg.status == "filled":
                total_credit += leg.entry_premium
            elif leg.action == "BUY" and leg.status == "filled":
                total_credit -= leg.entry_premium

        position.entry_credit = total_credit
        # Iron condor max_risk = max(put_width, call_width) - total_credit
        position.max_risk = candidate.max_risk
        position.status = "open"
        if not position.credit_counted:
            self.state.total_credit_collected += total_credit * candidate.contracts * 100
            position.credit_counted = True
        self._save_state()

        result["status"] = "open"
        result["net_credit"] = total_credit
        logger.info(f"IRON CONDOR OPEN: {spread_id} credit=${total_credit:.2f}")

        return result

    def _execute_side(
        self,
        position: SpreadPosition,
        candidate: SpreadCandidate,
        side: str,  # "put" or "call"
        dry_run: bool = False,
    ) -> bool:
        """Execute one side of a spread (long first, then short).

        Returns True if both legs filled successfully.
        """
        if side == "put":
            long_id = candidate.long_put_identifier
            long_strike = candidate.long_put_strike
            long_pc = "P"
            long_price = round(candidate.long_put_ask, 2)
            long_delta = candidate.long_put_delta
            short_id = candidate.short_put_identifier
            short_strike = candidate.short_put_strike
            short_pc = "P"
            short_price = round(candidate.short_put_bid, 2)
            short_delta = candidate.short_put_delta
        else:
            long_id = candidate.long_call_identifier
            long_strike = candidate.long_call_strike
            long_pc = "C"
            long_price = round(candidate.long_call_ask, 2)
            long_delta = candidate.long_call_delta
            short_id = candidate.short_call_identifier
            short_strike = candidate.short_call_strike
            short_pc = "C"
            short_price = round(candidate.short_call_bid, 2)
            short_delta = candidate.short_call_delta

        # BUY long leg
        long_leg = SpreadLeg(
            identifier=long_id, strike=long_strike, put_call=long_pc,
            action="BUY", contracts=candidate.contracts,
            entry_premium=long_price, status="pending",
            entry_delta=long_delta,
        )
        position.legs.append(long_leg)
        self._save_state()

        try:
            order_id = self.broker.place_option_market_order(
                identifier=long_id, action="BUY",
                quantity=candidate.contracts,
            )
            long_leg.order_id = order_id
            self._save_state()
        except Exception as e:
            logger.error(f"Long {side} leg order failed: {e}")
            long_leg.status = "error"
            self._save_state()
            return False

        fill_status = self._poll_for_fill(order_id, self.fill_timeout)
        if fill_status != "FILLED":
            self._cancel_order(order_id)
            long_leg.status = "cancelled"
            self._save_state()
            return False

        long_leg.status = "filled"
        self._save_state()

        # SELL short leg
        short_leg = SpreadLeg(
            identifier=short_id, strike=short_strike, put_call=short_pc,
            action="SELL", contracts=candidate.contracts,
            entry_premium=short_price, status="pending",
            entry_delta=short_delta,
        )
        position.legs.append(short_leg)

        if not options_risk.verify_no_naked_legs(position):
            logger.error(f"NAKED LEG CHECK FAILED on {side} side — aborting")
            short_leg.status = "error"
            self._save_state()
            self._emergency_close_leg(long_leg, position)
            return False

        self._save_state()

        try:
            order_id = self.broker.place_option_market_order(
                identifier=short_id, action="SELL",
                quantity=candidate.contracts,
            )
            short_leg.order_id = order_id
            self._save_state()
        except Exception as e:
            logger.error(f"Short {side} leg order failed: {e}")
            short_leg.status = "error"
            self._save_state()
            self._emergency_close_leg(long_leg, position)
            return False

        fill_status = self._poll_for_fill(order_id, self.fill_timeout)
        if fill_status != "FILLED":
            self._cancel_order(order_id)
            short_leg.status = "cancelled"
            self._save_state()
            self._emergency_close_leg(long_leg, position)
            return False

        short_leg.status = "filled"
        self._save_state()
        return True

    def close_spread(
        self,
        position: SpreadPosition,
        dry_run: bool = False,
    ) -> dict:
        """Close a spread by reversing all legs WITH fill confirmation.

        CLOSE ORDER: Short leg FIRST (buy back to remove obligation),
        POLL FOR FILL, then long leg (sell to close protection).
        If short close doesn't fill, do NOT sell long (would create naked short).
        """
        result = {
            "spread_id": position.spread_id,
            "status": "unknown",
        }

        if dry_run:
            result["status"] = "dry_run"
            logger.info(f"DRY RUN: Would close {position.spread_id}")
            return result

        position.status = "closing"
        self._save_state()

        # Get current quotes for all legs
        leg_identifiers = [leg.identifier for leg in position.legs if leg.status == "filled"]
        try:
            briefs = self.broker.get_option_briefs(leg_identifiers)
        except Exception as e:
            logger.error(f"Failed to get quotes for close: {e}")
            position.status = "open"  # revert so manage can retry
            self._save_state()
            result["status"] = "error_quotes"
            return result

        quote_map = {}
        for b in (briefs or []):
            ident = getattr(b, "identifier", "")
            bid = float(getattr(b, "bid_price", 0) or 0)
            ask = float(getattr(b, "ask_price", 0) or 0)
            if math.isnan(bid):
                bid = 0.0
                log_event("spreads", "nan_quote", identifier=ident, field="bid", context="close")
            if math.isnan(ask):
                ask = 0.0
                log_event("spreads", "nan_quote", identifier=ident, field="ask", context="close")
            quote_map[ident] = {"bid": bid, "ask": ask}

        total_debit = 0.0

        # Step 1: Close SHORT legs first (BUY back) — remove obligation
        short_legs = [l for l in position.legs if l.action == "SELL" and l.status == "filled"]
        for leg in short_legs:
            quote = quote_map.get(leg.identifier, {})
            close_price = round(quote.get("ask", 0), 2)  # reference only

            try:
                order_id = self.broker.place_option_market_order(
                    identifier=leg.identifier,
                    action="BUY",
                    quantity=leg.contracts,
                )
                logger.info(
                    f"Close short: BUY {leg.contracts} {leg.identifier} "
                    f"MARKET (ref ${close_price:.2f}) | order_id={order_id}"
                )
                self._save_state()
            except Exception as e:
                logger.error(f"Failed to close short leg {leg.identifier}: {e}")
                position.status = "open"  # revert so manage can retry
                self._save_state()
                result["status"] = "error_close_short"
                return result

            # CRITICAL: Poll for short close fill before selling long leg
            fill_status = self._poll_for_fill(order_id, self.fill_timeout)
            if fill_status != "FILLED":
                logger.warning(
                    f"Short close not filled ({fill_status}) for {leg.identifier} — "
                    f"aborting close to prevent naked short"
                )
                self._cancel_order(order_id)
                position.status = "open"  # revert so manage can retry
                self._save_state()
                result["status"] = f"error_short_close_not_filled_{fill_status.lower()}"
                self._notify(
                    f"ALERT: Close aborted for {position.spread_id} — "
                    f"short leg BUY-to-close not filled ({fill_status})"
                )
                return result

            total_debit += close_price
            leg.status = "closed"
            self._save_state()
            logger.info(f"Short close FILLED: {leg.identifier}")

        # Step 2: Close LONG legs (SELL) — safe since short obligation already removed
        long_legs = [l for l in position.legs if l.action == "BUY" and l.status == "filled"]
        for leg in long_legs:
            quote = quote_map.get(leg.identifier, {})
            close_price = round(quote.get("bid", 0), 2)  # reference only

            try:
                order_id = self.broker.place_option_market_order(
                    identifier=leg.identifier,
                    action="SELL",
                    quantity=leg.contracts,
                )
                logger.info(
                    f"Close long: SELL {leg.contracts} {leg.identifier} "
                    f"MARKET (ref ${close_price:.2f}) | order_id={order_id}"
                )
                self._save_state()
            except Exception as e:
                logger.error(f"Failed to close long leg {leg.identifier}: {e}")
                # Short already closed — long leg remains as a harmless long position.
                # Don't revert to "open" — short obligation is gone.
                # Mark as error so manage can see it and retry just the long close.
                position.status = "open"  # revert so manage can retry
                self._save_state()
                result["status"] = "error_close_long"
                return result

            # Poll for long close fill
            fill_status = self._poll_for_fill(order_id, self.fill_timeout)
            if fill_status != "FILLED":
                logger.warning(
                    f"Long close not filled ({fill_status}) for {leg.identifier} — "
                    f"cancelling (short already closed, no naked risk)"
                )
                self._cancel_order(order_id)
                # Short is closed but long isn't — revert so manage retries
                position.status = "open"  # revert so manage can retry
                self._save_state()
                result["status"] = f"error_long_close_not_filled_{fill_status.lower()}"
                return result

            total_debit -= close_price  # selling reduces debit
            leg.status = "closed"
            self._save_state()
            logger.info(f"Long close FILLED: {leg.identifier}")

        # Calculate P&L
        position.close_debit = total_debit
        position.close_date = date.today().isoformat()
        pnl = (position.entry_credit - total_debit) * position.contracts * 100
        position.realized_pnl = pnl
        self.state.total_realized_pnl += pnl
        self._save_state()

        result["status"] = "closed"
        result["close_debit"] = total_debit
        result["realized_pnl"] = pnl

        logger.info(
            f"SPREAD CLOSED: {position.spread_id} debit=${total_debit:.2f} "
            f"P&L=${pnl:,.0f}"
        )

        return result
