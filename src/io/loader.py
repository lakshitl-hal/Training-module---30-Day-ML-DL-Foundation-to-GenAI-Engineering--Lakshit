"""
Responsible for one thing: read rows from a CSV file.

CSVLoader does NOT validate, clean, or interpret data.
It returns raw dictionaries so that downstream classes decide
what to do with the values.

Field-count integrity:
    Every data row must contain exactly the same number of fields as the
    header.  A row with surplus fields would let csv.DictReader silently
    place the extra value under the key ``None``, shifting column meanings
    and corrupting ticket identifiers.  Such rows are rejected with a clear
    ValueError so callers never receive silently-corrupted data.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterator


class CSVLoader:
    """
    Load rows from a CSV file as plain dictionaries.

    Instance state:
        _path  – the resolved, validated path supplied at construction.

    Class state:
        SUPPORTED_EXTENSIONS – file types this loader accepts.
    """

    SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".csv"})

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path).resolve()
        self._validate_path()

    # --- public interface ----------------------------------------------------

    def load(self) -> list[dict[str, str]]:
        """Return all rows as a list of string-valued dicts.

        Raises:
            ValueError: if any row contains more fields than the header,
                        which would silently corrupt column alignment.
        """
        return list(self._iter_rows())

    def __repr__(self) -> str:
        return f"CSVLoader(path={str(self._path)!r})"

    # --- private helpers -----------------------------------------------------

    def _validate_path(self) -> None:
        if not self._path.exists():
            raise FileNotFoundError(f"File not found: {self._path}")
        if self._path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file type '{self._path.suffix}'. "
                f"Expected one of {sorted(self.SUPPORTED_EXTENSIONS)}"
            )

    def _iter_rows(self) -> Iterator[dict[str, str]]:
        with self._path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            expected_field_count: int = len(reader.fieldnames or [])

            for line_num, row in enumerate(reader, start=2):  # line 1 = header
                # csv.DictReader stores surplus fields under the key None.
                # Detect this and reject immediately with a clear message.
                if None in row:
                    surplus = row[None]  # type: ignore[index]
                    raise ValueError(
                        f"Row {line_num} has {expected_field_count + len(surplus)} "
                        f"fields but the header defines {expected_field_count}. "
                        f"Extra values: {surplus!r}. "
                        f"Malformed rows must be fixed before loading."
                    )
                yield dict(row)
