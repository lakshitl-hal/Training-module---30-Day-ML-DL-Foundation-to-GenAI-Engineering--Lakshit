"""
Command-line interface.

    python -m ticket_pipeline [--input PATH] [--log-level LEVEL] [--strict]

Output streams:
    stdout – the report (safe to redirect to a file)
    stderr – log records and error messages

Exit codes come from the exception class (``TicketPipelineError.exit_code``):
    0 success · 2 configuration · 3 input path · 4 malformed file ·
    5 schema mismatch · 6 rejected rows in strict mode

Only ``TicketPipelineError`` is caught. Any other exception is a bug, so it
is allowed to propagate with its full traceback instead of being hidden.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence

from ticket_pipeline.analytics.summary import format_summary
from ticket_pipeline.config import VALID_LOG_LEVELS, PipelineConfig
from ticket_pipeline.errors import TicketPipelineError
from ticket_pipeline.logging_config import configure_logging
from ticket_pipeline.pipeline import PipelineResult, run_pipeline

logger = logging.getLogger("ticket_pipeline.cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ticket_pipeline",
        description="Validate a support-ticket CSV file and print a summary.",
    )
    parser.add_argument("--input", help="CSV file to process (default: data/tickets.csv)")
    parser.add_argument(
        "--log-level", type=str.upper, choices=VALID_LOG_LEVELS,
        help="log verbosity (default: INFO, or $TICKET_PIPELINE_LOG_LEVEL)",
    )
    parser.add_argument(
        "--strict", action="store_true", help="exit with code 6 if any row is rejected"
    )
    return parser


def render_report(result: PipelineResult) -> str:
    lines = [
        f"Source: {result.source_name}",
        f"Rows read: {result.rows_read} | valid: {len(result.tickets)} "
        f"| rejected: {len(result.rejected)}",
    ]
    if result.rejected:
        lines.append("Rejected rows:")
        lines.extend(f"  - {error}" for error in result.rejected)
    lines.extend(["", format_summary(result.summary)])
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = PipelineConfig.from_sources(
            input_path=args.input, log_level=args.log_level, strict=args.strict
        )
        configure_logging(config.numeric_log_level)
        result = run_pipeline(config)
    except TicketPipelineError as exc:
        logger.error("status=failed error=%s exit_code=%d", type(exc).__name__, exc.exit_code)
        print(f"ERROR: {exc}", file=sys.stderr)
        return exc.exit_code

    print(render_report(result))
    return 0
