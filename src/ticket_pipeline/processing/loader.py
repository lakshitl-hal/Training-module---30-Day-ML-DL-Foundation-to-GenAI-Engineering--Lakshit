"""
CSV input: read raw rows from disk, lazily, with file-level integrity checks.

CSVLoader is responsible only for turning a file into ``RawRow`` objects.
It does not interpret cell values; TicketValidator does that.

File-level problems raise specific exceptions from ``ticket_pipeline.errors``
(the original low-level exception is kept as ``__cause__``):

    InputPathError       missing path, a directory, wrong extension, no permission
    MalformedFileError   empty file, bad encoding, duplicate/blank header names,
                         a row with more fields than the header, unparsable CSV
    SchemaMismatchError  required columns absent from the header
"""

from __future__ import annotations

import csv
import logging
from collections.abc import Collection, Generator, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from ticket_pipeline.errors import InputPathError, MalformedFileError, SchemaMismatchError

logger = logging.getLogger(__name__)

RowValues = dict[str, str]


@dataclass(frozen=True)
class RawRow:
    """One data row as read from the file.

    ``line`` is the physical line number in the file where the row starts,
    so every later message can point the user at the exact place to fix.
    """

    line: int
    values: RowValues


class CSVLoader:
    """Read a CSV file into ``RawRow`` objects.

    Class state:
        SUPPORTED_EXTENSIONS – file types this loader accepts (shared, immutable).
        ENCODING             – utf-8-sig, which also strips an Excel byte-order mark.
    Instance state:
        _path             – the path supplied by the caller.
        _required_columns – columns the header must contain (injected by the caller,
                            so the loader itself stays independent of the ticket schema).
    """

    SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".csv"})
    ENCODING: str = "utf-8-sig"

    def __init__(self, path: str | Path, required_columns: Collection[str] = ()) -> None:
        self._path = Path(path)
        self._required_columns = frozenset(required_columns)
        self._check_path()

    def __repr__(self) -> str:
        return f"CSVLoader(path={self._path.name!r})"

    # --- public interface ----------------------------------------------------

    def iter_rows(self) -> Generator[RawRow, None, None]:
        """Yield rows one at a time (lazy), closing the file when finished.

        The file is opened inside a ``with`` block, so it is closed when the
        generator is exhausted, when an error is raised, or when the caller
        stops iterating early and the generator is closed.
        """
        try:
            with self._path.open(newline="", encoding=self.ENCODING) as handle:
                yield from self._parse(handle)
        except UnicodeDecodeError as exc:
            raise MalformedFileError(
                self._path,
                f"File is not valid UTF-8 text (byte {exc.start})",
                "Re-save the file with UTF-8 encoding.",
            ) from exc
        except PermissionError as exc:
            raise InputPathError(
                self._path, "Permission denied reading input file",
                "Check that the file is not open in another program "
                "and that you have read access.",
            ) from exc

    def load(self) -> list[RawRow]:
        """Read every row into memory. Convenience wrapper over ``iter_rows``."""
        return list(self.iter_rows())

    # --- private helpers -----------------------------------------------------

    def _check_path(self) -> None:
        if not self._path.exists():
            raise InputPathError(
                self._path, "Input file not found",
                "Check the path, or pass --input with the correct location.",
            )
        if not self._path.is_file():
            raise InputPathError(
                self._path, "Input path is not a file",
                "Pass the path of a .csv file, not a directory.",
            )
        if self._path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            raise InputPathError(
                self._path, f"Unsupported file type '{self._path.suffix or '(none)'}'",
                f"Provide a file ending in {', '.join(sorted(self.SUPPORTED_EXTENSIONS))}.",
            )

    def _parse(self, handle: TextIO) -> Iterator[RawRow]:
        reader = csv.reader(handle)
        try:
            header = self._read_header(reader)
            for fields in reader:
                # reader.line_num is the physical line just read. It stays
                # correct when blank lines are skipped or a quoted field
                # spans several lines (enumerate() would drift).
                line = reader.line_num
                if not fields:  # blank line
                    continue
                if len(fields) > len(header):
                    raise MalformedFileError(
                        self._path,
                        f"Row has {len(fields)} fields but the header defines "
                        f"{len(header)}",
                        "Remove the extra field(s) or quote values that contain commas.",
                        line=line,
                    )
                # Short rows are padded with "" so the validator can report
                # exactly which required values are missing.
                padded = fields + [""] * (len(header) - len(fields))
                yield RawRow(line=line, values=dict(zip(header, padded, strict=True)))
        except csv.Error as exc:
            raise MalformedFileError(
                self._path, f"CSV could not be parsed ({exc})",
                "Check for unbalanced quotes or binary content.",
                line=reader.line_num,
            ) from exc

    def _read_header(self, reader: Iterator[list[str]]) -> list[str]:
        raw_header = next(reader, None)
        if raw_header is None:
            raise MalformedFileError(
                self._path, "File is empty",
                "Add a header row: the first line must list the column names.",
            )
        header = [name.strip().lower() for name in raw_header]

        blanks = [i + 1 for i, name in enumerate(header) if not name]
        if blanks:
            raise MalformedFileError(
                self._path, f"Header has blank column name(s) at position(s) "
                f"{', '.join(map(str, blanks))}",
                "Name every column, or remove trailing commas from the header.",
                line=1,
            )
        duplicates = sorted({name for name in header if header.count(name) > 1})
        if duplicates:
            raise MalformedFileError(
                self._path, f"Header repeats column(s): {', '.join(duplicates)}",
                "Each column name must appear once.",
                line=1,
            )
        missing = self._required_columns.difference(header)
        if missing:
            raise SchemaMismatchError(self._path, missing=missing, found=header)

        logger.debug("file=%s columns=%d", self._path.name, len(header))
        return header
