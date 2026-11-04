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
from ticket_pipeline.errors import InvalidRowError, RejectedRowsError
from ticket_pipeline.logging_config import log_duration
from ticket_pipeline.models.ticket import Ticket
from ticket_pipeline.processing.loader import CSVLoader
from ticket_pipeline.processing.parser import REQUIRED_COLUMNS, parse_row

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineResult:
    source_name: str
    rows_read: int
    tickets: tuple[Ticket, ...]
    rejected: tuple[InvalidRowError, ...]
    summary: TicketSummary


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
        try:
            ticket = parse_row(row)
            if ticket.ticket_id in first_line_for_id:
                raise InvalidRowError(
                    row.line, "ticket_id",
                    f"duplicate of line {first_line_for_id[ticket.ticket_id]}",
                )
        except InvalidRowError as exc:
            # Log the line and column only — never the row's values.
            logger.warning(
                "stage=parse status=rejected line=%d column=%s", exc.line, exc.column
            )
            rejected.append(exc)
            continue
        first_line_for_id[ticket.ticket_id] = row.line
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
