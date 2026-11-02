"""Command-line entry point for ticket cleaning, analytics, and EDA."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Sequence

import pandas as pd

from ticket_analytics.analytics import (
    build_analytics_report,
    build_data_quality_summary,
)
from ticket_analytics.eda import build_eda_report
from ticket_analytics.processor import TicketDataProcessor, TicketProcessingError
from ticket_analytics.reporting import export_pipeline_outputs, print_report

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = PROJECT_ROOT / "data" / "tickets_synthetic.csv"

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def _run_analysis(input_path: Path, output_dir: Path) -> int:
    processor = TicketDataProcessor(input_path)
    try:
        cleaned = processor.process()
    except TicketProcessingError as exc:
        logger.error("Pipeline failed: %s", exc)
        return 1

    validation = processor.validation_report
    raw = processor.raw
    if raw is None:
        raise RuntimeError("The processor completed without retaining its raw data.")

    report = build_analytics_report(cleaned)
    report["data_quality"] = build_data_quality_summary(validation)
    written = export_pipeline_outputs(report, processor.quality_issues, output_dir)
    eda_path = output_dir / "eda_report.json"
    eda_path.write_text(
        json.dumps(build_eda_report(raw), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("\nTicket data validation")
    print(f"  Raw rows             : {validation['rows_in_raw']}")
    print(f"  Rows after cleaning  : {validation['rows_after_cleaning']}")
    print(f"  Quality issues       : {validation['issue_count']}")
    for issue in validation["invalid_records"]:
        print(f"  Data-quality issue   : {issue}")
    print_report(report)
    print(f"Reports written to: {output_dir.resolve()}")
    for path in written:
        print(f"  {path.name}")
    print(f"  {eda_path.name}")
    return 0


def _run_eda(input_path: Path, output_path: Path | None) -> int:
    try:
        raw = pd.read_csv(input_path, dtype=str, keep_default_na=False)
    except (
        OSError,
        UnicodeDecodeError,
        pd.errors.EmptyDataError,
        pd.errors.ParserError,
    ) as exc:
        logger.error("Could not read dataset '%s': %s", input_path, exc)
        return 1

    report = build_eda_report(raw)
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    if output_path is None:
        print(rendered)
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")
        print(f"EDA report written to {output_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ticket-analytics",
        description="Clean, analyze, and profile support-ticket CSV datasets.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=("analyze", "eda"),
        default="analyze",
        help="run the cleaning/analytics pipeline or raw-data EDA (default: analyze)",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_DATASET,
        help=f"input CSV path (default: {DEFAULT_DATASET})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="optional JSON destination (used by the eda command)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "outputs",
        help="directory for analyze CSV and EDA outputs (default: outputs)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf_8"):
            sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

    args = build_parser().parse_args(argv)
    if args.command == "eda":
        if args.output_dir != PROJECT_ROOT / "outputs":
            build_parser().error("--output-dir can only be used with the analyze command")
        return _run_eda(args.input, args.output)
    if args.output is not None:
        build_parser().error("--output can only be used with the eda command")
    return _run_analysis(args.input, args.output_dir)
