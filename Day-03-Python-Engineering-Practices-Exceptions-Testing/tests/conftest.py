"""
Shared fixtures.

Determinism rules applied to every test:
    * files are created in pytest's per-test ``tmp_path``, never in the repo;
    * the TICKET_PIPELINE_* environment variables are removed;
    * logger configuration is restored after each test;
so each test can run alone, in any order, on any machine.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from sample_data import HEADER, VALID_ROWS, WriteCsv


@pytest.fixture(autouse=True)
def _isolate_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for name in ("TICKET_PIPELINE_INPUT", "TICKET_PIPELINE_LOG_LEVEL"):
        monkeypatch.delenv(name, raising=False)
    package_logger = logging.getLogger("ticket_pipeline")
    saved = (package_logger.handlers[:], package_logger.level, package_logger.propagate)
    yield
    package_logger.handlers[:], package_logger.level, package_logger.propagate = saved


@pytest.fixture
def write_csv(tmp_path: Path) -> WriteCsv:
    """Factory: write CSV text to a temporary file and return its path.

    ``rows`` are appended under ``header``; pass ``header=None`` to write
    ``rows`` exactly as given (for malformed-file tests).
    """

    def _write(
        *rows: str,
        header: str | None = HEADER,
        name: str = "tickets.csv",
        encoding: str = "utf-8",
    ) -> Path:
        lines = ([header] if header is not None else []) + list(rows)
        path = tmp_path / name
        path.write_bytes(("\n".join(lines) + "\n" if lines else "").encode(encoding))
        return path

    return _write


@pytest.fixture
def sample_csv(write_csv: WriteCsv) -> Path:
    """A small file with three valid rows."""
    return write_csv(*VALID_ROWS)
