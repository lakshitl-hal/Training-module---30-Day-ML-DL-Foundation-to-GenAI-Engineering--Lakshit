"""
Exception hierarchy for the ticket pipeline.

Every error the pipeline raises on purpose derives from TicketPipelineError,
so callers can catch "any expected pipeline failure" in one place while
programming errors (bugs) still surface as ordinary exceptions.

Each error message states three things so it is actionable:
    1. what went wrong,
    2. where (file name, line, column),
    3. how to fix it.

Messages never contain personal data. Free-text columns (customer,
description) are never echoed; only coded values (priority, status, dates,
numbers) may be quoted, because the user needs them to find the bad cell.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path


class TicketPipelineError(Exception):
    """Base class for all expected pipeline failures.

    ``exit_code`` lets the command-line interface map each failure type to
    a distinct process exit status without a chain of ``isinstance`` checks.
    """

    exit_code: int = 1


class ConfigurationError(TicketPipelineError):
    """The pipeline was configured with an invalid setting."""

    exit_code = 2


class InputPathError(TicketPipelineError):
    """The input path does not point at a usable CSV file."""

    exit_code = 3

    def __init__(self, path: Path, problem: str, hint: str) -> None:
        self.path = path
        super().__init__(f"{problem}: '{path}'. {hint}")


class MalformedFileError(TicketPipelineError):
    """The file exists but its contents cannot be parsed as the expected CSV."""

    exit_code = 4

    def __init__(
        self, path: Path, problem: str, hint: str, line: int | None = None
    ) -> None:
        self.path = path
        self.line = line
        location = f"{path.name}, line {line}" if line is not None else path.name
        super().__init__(f"{problem} ({location}). {hint}")


@dataclass(frozen=True)
class RowIssue:
    """One problem in one cell: which column, and why."""

    column: str
    reason: str

    def __str__(self) -> str:
        return f"'{self.column}' {self.reason}"


class InvalidRowError(TicketPipelineError):
    """One data row breaks one or more business rules.

    This is *recoverable*: the pipeline catches it per row, records the
    rejection and continues with the next row. All problems found in the
    row are reported together, so the file can be fixed in one pass.
    """

    def __init__(self, line: int, issues: Sequence[RowIssue]) -> None:
        if not issues:
            raise ValueError("InvalidRowError needs at least one issue")
        self.line = line
        self.issues: tuple[RowIssue, ...] = tuple(issues)
        super().__init__(f"line {line}: {'; '.join(map(str, self.issues))}")

    @property
    def columns(self) -> tuple[str, ...]:
        return tuple(issue.column for issue in self.issues)


class RejectedRowsError(TicketPipelineError):
    """Raised in strict mode when one or more rows were rejected."""

    exit_code = 6

    def __init__(self, rejected: Sequence[InvalidRowError], total: int) -> None:
        self.rejected: tuple[InvalidRowError, ...] = tuple(rejected)
        self.total = total
        # The rows are listed in the message itself, so the error stays
        # actionable even when WARNING-level logs are switched off.
        details = "\n".join(f"  - {error}" for error in self.rejected)
        super().__init__(
            f"{len(self.rejected)} of {total} row(s) were rejected and strict mode is on:\n"
            f"{details}\n"
            f"Fix these rows, or run without --strict to skip them."
        )


class SchemaMismatchError(TicketPipelineError):
    """The CSV header does not contain the columns the pipeline requires."""

    exit_code = 5

    def __init__(
        self, path: Path, missing: Iterable[str], found: Iterable[str]
    ) -> None:
        self.path = path
        self.missing: tuple[str, ...] = tuple(sorted(missing))
        self.found: tuple[str, ...] = tuple(found)
        super().__init__(
            f"{path.name} is missing required column(s): "
            f"{', '.join(self.missing)}. "
            f"Found columns: {', '.join(self.found) or '(none)'}. "
            f"Add the missing column(s) to the header row."
        )
