"""
Pipeline orchestration: load -> parse -> de-duplicate -> summarise.

Error-handling policy:
    * File-level problems (InputPathError, MalformedFileError,
      SchemaMismatchError) are *not* caught here. They propagate to the
      caller, because no useful result can be produced.
    * Row-level problems (InvalidRowError) are caught one row at a time,
      logged with line and column, and collected in ``PipelineResult.rejected``.
      Only that specific exception is caught; a bug elsewhere still fails loudly.
    * In strict mode, any rejected row raises RejectedRowsError at the end.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ticket_pipeline.analytics.summary import TicketSummary, summarise
from ticket_pipeline.config import PipelineConfig
from ticket_pipeline.errors import InvalidRowError, RejectedRowsError, RowIssue
from ticket_pipeline.logging_config import log_duration
from ticket_pipeline.models.ticket import Ticket
from ticket_pipeline.processing.loader import CSVLoader, RawRow
from ticket_pipeline.processing.parser import REQUIRED_COLUMNS, parse_row

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineResult:
    source_name: str
    rows_read: int
    tickets: tuple[Ticket, ...]
    rejected: tuple[InvalidRowError, ...]
    summary: TicketSummary


def _check_duplicate_id(row: RawRow, first_line_for_id: dict[str, int]) -> RowIssue | None:
    """Record the row's ID; return an issue if an earlier row used it.

    Every row with an ID is recorded, valid or not, so a duplicate is still
    reported after the earlier row is fixed. IDs that differ only by case or
    surrounding spaces ('T1', ' t1 ') are treated as the same ticket.
    """
    id_key = row.values.get("id", "").strip().casefold()
    if not id_key:
        return None  # an empty ID is reported by the parser
    if id_key in first_line_for_id:
        return RowIssue("id", f"duplicates line {first_line_for_id[id_key]}")
    first_line_for_id[id_key] = row.line
    return None


@log_duration("pipeline")
def run_pipeline(config: PipelineConfig) -> PipelineResult:
    """Run every stage for ``config.input_path`` and return the result."""
    loader = CSVLoader(config.input_path, required_columns=REQUIRED_COLUMNS)
    source = config.input_path.name
    logger.info("stage=load status=started file=%s", source)

    tickets: list[Ticket] = []
    rejected: list[InvalidRowError] = []
    first_line_for_id: dict[str, int] = {}
    rows_read = 0

    for row in loader.iter_rows():  # lazy: one row in memory at a time
        rows_read += 1
        duplicate = _check_duplicate_id(row, first_line_for_id)
        try:
            ticket = parse_row(row)
            if duplicate is not None:
                raise InvalidRowError(row.line, [duplicate])
        except InvalidRowError as exc:
            error = exc
            if duplicate is not None and duplicate not in exc.issues:
                # The row has other problems too: report all of them together.
                error = InvalidRowError(row.line, [*exc.issues, duplicate])
                error.__cause__ = exc.__cause__
            # Log the line and column names only - never the row's values.
            logger.warning(
                "stage=parse status=rejected line=%d columns=%s",
                error.line, ",".join(error.columns),
            )
            rejected.append(error)
            continue
        tickets.append(ticket)

    logger.info(
        "stage=parse status=completed file=%s rows=%d valid=%d rejected=%d",
        source, rows_read, len(tickets), len(rejected),
    )
    if rows_read == 0:
        logger.warning("stage=load status=empty file=%s detail=header-only", source)

    if config.strict and rejected:
        raise RejectedRowsError(rejected=rejected, total=rows_read)

    return PipelineResult(
        source_name=source,
        rows_read=rows_read,
        tickets=tuple(tickets),
        rejected=tuple(rejected),
        summary=summarise(tickets),
    )
