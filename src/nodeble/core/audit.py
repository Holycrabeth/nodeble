# -*- coding: utf-8 -*-
"""Append-only event audit log.

Writes one JSON line per event to ~/.nodeble/data/audit/events_YYYY-MM-DD.jsonl.
Fail-open: never crashes the caller.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from nodeble.paths import get_data_dir

NY = ZoneInfo("America/New_York")

logger = logging.getLogger(__name__)


def log_event(strategy: str, event_type: str, **kwargs) -> None:
    """Append a single audit event. Never raises."""
    try:
        now = datetime.now(NY)
        record = {
            "ts": now.isoformat(),
            "strategy": strategy,
            "event": event_type,
            **kwargs,
        }
        audit_dir = get_data_dir() / "data" / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        path = audit_dir / f"events_{now.strftime('%Y-%m-%d')}.jsonl"
        with open(path, "a") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except Exception as e:
        logger.warning(f"audit.log_event failed: {e}")
