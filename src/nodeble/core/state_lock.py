# -*- coding: utf-8 -*-
"""File locking for state read-modify-write cycles.

Prevents concurrent jobs from clobbering each other's state writes.
Uses fcntl.flock() with non-blocking retries.
"""

import fcntl
import logging
import time
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY = 1.0  # seconds


@contextmanager
def state_lock(state_path: str):
    """Acquire an exclusive file lock for a state file.

    Usage:
        with state_lock("data/state_theta.json"):
            data = load(...)
            modify(data)
            save(data, ...)

    Uses <state_file>.lock as the lock file. Non-blocking with retries:
    tries 3 times, 1 second apart. If lock can't be acquired, raises
    an error (caller decides whether to skip the write or abort).

    Lock files are created in the same directory as the state file.
    """
    lock_path = Path(state_path).with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    lock_fd = None
    try:
        lock_fd = open(lock_path, "w")

        for attempt in range(MAX_RETRIES):
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                logger.debug(f"State lock acquired: {lock_path}")
                yield
                return
            except (IOError, OSError):
                if attempt < MAX_RETRIES - 1:
                    logger.warning(
                        f"State lock busy ({lock_path}), retry {attempt + 1}/{MAX_RETRIES}"
                    )
                    time.sleep(RETRY_DELAY)
                else:
                    logger.error(
                        f"State lock failed after {MAX_RETRIES} attempts: {lock_path}"
                    )
                    raise
    finally:
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except Exception:
                pass
            lock_fd.close()
