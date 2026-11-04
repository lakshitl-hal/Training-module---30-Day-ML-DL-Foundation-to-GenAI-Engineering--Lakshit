"""
Logging setup and helpers.

Library modules only *emit* records through ``logging.getLogger(__name__)``;
they never configure handlers. Configuration happens once, in the CLI, via
``configure_logging``. This keeps log output under the application's control
and lets tests capture records with pytest's ``caplog``.

Logging policy (what is and is not logged):
    Logged:     stage boundaries, row/line numbers, ticket IDs, column names,
                counts, durations, file *names*, error categories.
    Not logged: customer names, descriptions, any raw cell value, full
                file-system paths (they can reveal user names).
"""

from __future__ import annotations

import functools
import logging
import sys
import time
from collections.abc import Callable
from typing import ParamSpec, TypeVar

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s | %(message)s"

P = ParamSpec("P")
R = TypeVar("R")


def configure_logging(level: int = logging.INFO) -> None:
    """Send log records to stderr so they never mix with report output."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root = logging.getLogger("ticket_pipeline")
    root.handlers.clear()  # idempotent: safe to call more than once
    root.addHandler(handler)
    root.setLevel(level)
    root.propagate = False


def log_duration(stage: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator: log how long ``stage`` took, at DEBUG level.

    The duration is logged even if the wrapped function raises, and the
    exception is re-raised unchanged so the root cause is never hidden.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        logger = logging.getLogger(func.__module__)

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            start = time.perf_counter()
            outcome = "failed"
            try:
                result = func(*args, **kwargs)
                outcome = "completed"
                return result
            finally:
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.debug(
                    "stage=%s outcome=%s duration_ms=%.1f", stage, outcome, elapsed_ms
                )

        return wrapper

    return decorator
