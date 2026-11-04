"""Sample ticket CSV content shared by the tests (plain constants, no fixtures)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

HEADER = (
    "id,customer,priority,category,status,description,"
    "resolution_time_hours,customer_rating,created_at"
)

VALID_ROWS = (
    "T001,alice johnson,high,billing,open,Cannot access invoice,,,2024-01-15",
    "T002,Bob Smith,low,technical,closed,App crashes on startup,4,4,2024-01-16",
    "T003,Carol White,URGENT,account,pending,Cannot log in,2,5,2024-01-16",
)

WriteCsv = Callable[..., Path]  # type of the write_csv fixture
