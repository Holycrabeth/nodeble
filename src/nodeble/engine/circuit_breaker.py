"""Intraday circuit breaker — monitors portfolio drawdown from start-of-day NLV.

Levels:
  green  — no drawdown concern
  yellow — -2% NLV warning (info only)
  orange — -3% NLV block new positions
  red    — -5% NLV block + cancel pending orders

Fail-open: returns green if broker unavailable or state missing.
"""

import json
import logging
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from nodeble.paths import get_data_dir

logger = logging.getLogger(__name__)

NY = ZoneInfo("America/New_York")


class CircuitBreaker:
    """Intraday portfolio drawdown circuit breaker."""

    LEVELS = {
        "green": 0,
        "yellow": -0.02,
        "orange": -0.03,
        "red": -0.05,
    }

    def __init__(self):
        self._state_path = get_data_dir() / "data" / "circuit_breaker.json"

    @property
    def STATE_PATH(self):
        return self._state_path

    def check(self, broker=None) -> str:
        """Returns current level: green/yellow/orange/red."""
        state = self._load_state()
        today_str = date.today().isoformat()

        if state.get("sod_date") != today_str or not state.get("sod_nlv"):
            return "green"

        sod_nlv = state["sod_nlv"]
        current_nlv = self._get_current_nlv(broker, sod_nlv)

        drawdown_pct = (current_nlv - sod_nlv) / sod_nlv if sod_nlv > 0 else 0.0

        level = "green"
        for lv in ("red", "orange", "yellow"):
            if drawdown_pct <= self.LEVELS[lv]:
                level = lv
                break

        now = datetime.now(NY)
        state["last_check"] = now.strftime("%Y-%m-%d %H:%M ET")
        state["current_level"] = level
        state["current_drawdown_pct"] = round(drawdown_pct, 6)
        state["current_nlv"] = round(current_nlv, 2)
        self._save_state(state)

        return level

    def record_sod_nlv(self, nlv: float):
        today_str = date.today().isoformat()
        state = self._load_state()
        state["sod_nlv"] = round(nlv, 2)
        state["sod_date"] = today_str
        state["current_level"] = "green"
        state["current_drawdown_pct"] = 0.0
        now = datetime.now(NY)
        state["last_check"] = now.strftime("%Y-%m-%d %H:%M ET")
        self._save_state(state)
        logger.info(f"Circuit breaker: recorded SOD NLV ${nlv:,.2f}")

    def maybe_record_sod(self, broker):
        try:
            state = self._load_state()
            today_str = date.today().isoformat()
            if state.get("sod_date") == today_str and state.get("sod_nlv"):
                return
            nlv = self._get_nlv_from_broker(broker)
            if nlv and nlv > 0:
                self.record_sod_nlv(nlv)
        except Exception as e:
            logger.warning(f"Circuit breaker: failed to record SOD NLV: {e}")

    def is_blocked(self, broker=None) -> tuple[bool, str]:
        level = self.check(broker)
        blocked = level in ("orange", "red")
        return blocked, level

    def get_status(self) -> dict:
        return self._load_state()

    def _get_current_nlv(self, broker, fallback: float) -> float:
        if broker:
            nlv = self._get_nlv_from_broker(broker)
            if nlv and nlv > 0:
                return nlv
        return fallback

    def _get_nlv_from_broker(self, broker) -> float | None:
        if not broker:
            return None
        try:
            assets = broker.get_assets()
            seg = assets.segments.get("S") if hasattr(assets, "segments") else None
            if seg:
                return getattr(seg, "net_liquidation", 0) or 0
        except Exception as e:
            logger.warning(f"Circuit breaker: broker NLV fetch failed: {e}")
        return None

    def _load_state(self) -> dict:
        if self._state_path.exists():
            try:
                with open(self._state_path) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Circuit breaker: failed to load state: {e}")
        return {}

    def _save_state(self, data: dict):
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._state_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"Circuit breaker: failed to save state: {e}")
