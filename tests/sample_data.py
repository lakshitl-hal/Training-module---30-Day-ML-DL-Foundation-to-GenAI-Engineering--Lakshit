"""Sample CSV content shared by the tests (plain constants, no fixtures)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

HEADER = "ticket_id,customer_email,priority,status,category,created_at,resolution_hours"

VALID_ROWS = (
    "TKT-0001,asha@example.com,high,open,billing,2026-10-01,",
    "TKT-0002,ben@example.com,low,resolved,technical,2026-10-01,4",
    "TKT-0003,chen@example.com,urgent,closed,account,2026-10-02,8",
)

WriteCsv = Callable[..., Path]  # type of the write_csv fixture
