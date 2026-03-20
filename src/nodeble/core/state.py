# -*- coding: utf-8 -*-
"""Options spread state tracking: positions, legs, P&L."""

import json
import logging
import os
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SpreadLeg:
    """Single leg of a spread."""

    identifier: str  # e.g. "TSLA  260327P00250000"
    strike: float  # 250.0
    put_call: str  # "P" or "C"
    action: str  # "BUY" or "SELL"
    contracts: int  # 1
    entry_premium: float  # per share
    order_id: int = 0
    status: str = "pending"  # pending/filled/cancelled/expired/error
    entry_delta: float = 0.0  # actual delta at entry (negative for puts, positive for calls)


@dataclass
class SpreadPosition:
    """A complete spread position (vertical or iron condor)."""

    spread_id: str  # e.g. "TSLA_bull_put_2026-03-27_250_245"
    underlying: str  # "TSLA"
    expiry: str  # "2026-03-27"
    spread_type: str  # bull_put / bear_call / iron_condor
    legs: list[SpreadLeg] = field(default_factory=list)
    entry_date: str = ""
    entry_credit: float = 0.0  # net credit received per share
    max_risk: float = 0.0  # spread width - credit (per share)
    contracts: int = 1
    status: str = "pending"  # pending/open/partial/closing/closed_profit/closed_stop/closed_dte/expired/error
    close_date: str = ""
    close_debit: float = 0.0  # cost to close per share
    realized_pnl: float = 0.0  # total P&L (credit - debit) * contracts * 100
    current_value: float = 0.0  # current cost to close
    current_dte: int = 0
    credit_counted: bool = False  # prevents double-counting total_credit_collected on crash recovery
    nan_quote_streak: int = 0  # consecutive manage cycles with NaN/missing quotes


@dataclass
class SpreadState:
    """Full options spread strategy state."""

    positions: dict[str, SpreadPosition] = field(default_factory=dict)
    last_scan_date: str = ""
    last_manage_date: str = ""
    total_credit_collected: float = 0.0
    total_realized_pnl: float = 0.0

    def get_open_positions(self) -> list[SpreadPosition]:
        """Positions confirmed open (all legs filled)."""
        return [p for p in self.positions.values() if p.status == "open"]

    def get_active_positions(self) -> list[SpreadPosition]:
        """Positions counting toward risk limits (open + pending + partial)."""
        return [
            p for p in self.positions.values()
            if p.status in ("open", "pending", "partial")
        ]

    def get_active_count(self) -> int:
        return len(self.get_active_positions())

    def get_symbol_count(self, symbol: str) -> int:
        return sum(
            1 for p in self.positions.values()
            if p.status in ("open", "pending", "partial") and p.underlying == symbol
        )

    def get_total_exposure(self) -> float:
        """Total max risk exposure: sum of max_risk * contracts * 100."""
        return sum(
            p.max_risk * p.contracts * 100
            for p in self.positions.values()
            if p.status in ("open", "pending", "partial")
        )

    def get_total_delta(self) -> float:
        """Portfolio delta from spread positions using actual per-leg deltas."""
        total = 0.0
        for p in self.positions.values():
            if p.status not in ("open", "pending", "partial"):
                continue

            pos_delta = 0.0
            has_real_delta = False
            for leg in p.legs:
                if leg.status not in ("filled", "pending"):
                    continue
                if leg.entry_delta != 0:
                    has_real_delta = True
                    if leg.action == "SELL":
                        pos_delta += -leg.entry_delta
                    else:
                        pos_delta += leg.entry_delta

            if has_real_delta:
                total += pos_delta * p.contracts * 100
            else:
                if p.spread_type == "bull_put":
                    total += 0.10 * p.contracts * 100
                elif p.spread_type == "bear_call":
                    total += -0.10 * p.contracts * 100
        return total

    def get_daily_pnl(self, today_str: str) -> float:
        """Realized P&L from positions closed today."""
        return sum(
            p.realized_pnl
            for p in self.positions.values()
            if p.close_date == today_str
        )

    def save(self, path: str) -> None:
        from nodeble.core.state_lock import state_lock
        with state_lock(path):
            self._write(path)

    def _write(self, path: str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "last_scan_date": self.last_scan_date,
            "last_manage_date": self.last_manage_date,
            "total_credit_collected": self.total_credit_collected,
            "total_realized_pnl": self.total_realized_pnl,
            "positions": {},
        }
        for k, v in self.positions.items():
            pos_dict = asdict(v)
            data["positions"][k] = pos_dict
        # Atomic write: temp file + rename prevents corruption on crash
        fd, tmp_path = tempfile.mkstemp(dir=p.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, p)
        except BaseException:
            os.unlink(tmp_path)
            raise
        logger.info(f"Spread state saved: {len(self.positions)} positions -> {path}")

    @classmethod
    def load(cls, path: str) -> "SpreadState":
        p = Path(path)
        if not p.exists():
            logger.info(f"No spread state at {path}, starting fresh")
            return cls()
        with open(p) as f:
            data = json.load(f)
        state = cls(
            last_scan_date=data.get("last_scan_date", ""),
            last_manage_date=data.get("last_manage_date", ""),
            total_credit_collected=data.get("total_credit_collected", 0.0),
            total_realized_pnl=data.get("total_realized_pnl", 0.0),
        )
        for key, pos_data in data.get("positions", {}).items():
            legs_raw = pos_data.pop("legs", [])
            legs = [SpreadLeg(**leg) for leg in legs_raw]
            state.positions[key] = SpreadPosition(legs=legs, **pos_data)
        logger.info(f"Spread state loaded: {len(state.positions)} positions from {path}")
        return state
