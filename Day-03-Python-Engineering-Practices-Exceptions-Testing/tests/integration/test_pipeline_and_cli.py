"""
Integration tests: the real loader, parser, pipeline and CLI working together
on real temporary files. Nothing internal is mocked, except one test that
simulates a bug to prove it is not hidden.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from sample_data import VALID_ROWS, WriteCsv
from ticket_pipeline.cli import main
from ticket_pipeline.config import DEFAULT_INPUT_PATH, PipelineConfig
from ticket_pipeline.errors import RejectedRowsError
from ticket_pipeline.pipeline import run_pipeline

pytestmark = pytest.mark.integration

BAD_ROWS = (
    "T004,Dana Cruz,critical,billing,open,Refund request,,,2024-01-17",   # line 5: priority
    "t001,Eve Stone,low,general,open,Second copy of T001,,,2024-01-17",    # line 6: duplicate
)


# --- behaviour preserved from the existing ticket pipeline -----------------

def test_bundled_dataset_keeps_the_established_results() -> None:
    """Regression: data/tickets.csv must produce the same results as the
    existing ticket pipeline (7 valid tickets, rows on lines 4, 7, 9 rejected)."""
    result = run_pipeline(PipelineConfig(input_path=DEFAULT_INPUT_PATH))
    summary = result.summary

    assert (result.rows_read, summary.total) == (10, 7)
    assert [(e.line, e.columns) for e in result.rejected] == [
        (4, ("customer",)), (7, ("description",)), (9, ("customer", "category")),
    ]
    assert summary.by_priority == {"high": 2, "low": 2, "medium": 2, "urgent": 1}
    assert summary.by_status == {"closed": 2, "open": 2, "pending": 2, "resolved": 1}
    assert summary.by_category == {"account": 1, "billing": 2, "technical": 3, "unknown": 1}
    assert summary.open_count == 4
    assert summary.high_priority_open_ids == ("T001", "T004", "T009")
    assert summary.average_resolution_hours == 3.8
    assert summary.average_rating == 3.83
    assert len(summary.daily_volume) == 7 and set(summary.daily_volume.values()) == {1}


# --- pipeline behaviour ------------------------------------------------------

def test_valid_file_produces_tickets_and_summary(sample_csv: Path) -> None:
    result = run_pipeline(PipelineConfig(input_path=sample_csv))
    assert [t.ticket_id for t in result.tickets] == ["T001", "T002", "T003"]
    assert result.rejected == ()
    assert result.summary.average_resolution_hours == 3.0


def test_bad_rows_are_rejected_but_good_rows_kept(write_csv: WriteCsv) -> None:
    result = run_pipeline(PipelineConfig(input_path=write_csv(*VALID_ROWS, *BAD_ROWS)))
    assert len(result.tickets) == 3
    assert [(e.line, e.columns) for e in result.rejected] == [(5, ("priority",)), (6, ("id",))]
    assert "'id' duplicates line 2" in str(result.rejected[1])  # 't001' == 'T001'


def test_strict_mode_fails_and_carries_the_rejected_rows(write_csv: WriteCsv) -> None:
    path = write_csv(*VALID_ROWS, *BAD_ROWS)
    with pytest.raises(RejectedRowsError, match="2 of 5 row") as info:
        run_pipeline(PipelineConfig(input_path=path, strict=True))
    assert [e.line for e in info.value.rejected] == [5, 6]


def test_logs_describe_stages_without_personal_data(
    write_csv: WriteCsv, caplog: pytest.LogCaptureFixture
) -> None:
    path = write_csv(*VALID_ROWS, *BAD_ROWS)
    with caplog.at_level(logging.DEBUG, logger="ticket_pipeline"):
        run_pipeline(PipelineConfig(input_path=path))
    assert "stage=load status=started file=tickets.csv" in caplog.text
    assert "status=rejected line=5 columns=priority" in caplog.text
    assert "rows=5 valid=3 rejected=2" in caplog.text
    assert "stage=pipeline outcome=completed" in caplog.text
    for private in ("Alice", "Bob Smith", "Dana Cruz", "Cannot access invoice", "Refund"):
        assert private not in caplog.text          # no names or descriptions
    assert str(path.parent) not in caplog.text     # no full file-system paths


def test_header_only_file_logs_warning(
    write_csv: WriteCsv, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="ticket_pipeline"):
        result = run_pipeline(PipelineConfig(input_path=write_csv()))
    assert result.rows_read == 0
    assert "status=empty" in caplog.text


# --- command-line interface ----------------------------------------------------

class TestCommandLine:
    def test_success_prints_report_to_stdout_and_logs_to_stderr(
        self, sample_csv: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["--input", str(sample_csv)]) == 0
        out, err = capsys.readouterr()
        assert "Rows read: 3 | valid: 3 | rejected: 0" in out
        assert "stage=load" in err and "stage=load" not in out

    def test_rejected_rows_are_listed_without_personal_data(
        self, write_csv: WriteCsv, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["--input", str(write_csv(*VALID_ROWS, *BAD_ROWS))]) == 0
        out, err = capsys.readouterr()
        assert "line 5: 'priority' value 'critical' is not one of" in out
        assert "Dana Cruz" not in out + err and "Refund" not in out + err

    @pytest.mark.parametrize(
        ("setup", "exit_code", "message"),
        [
            ("missing", 3, "Input file not found"),
            ("empty", 4, "File is empty"),
            ("duplicate-header", 4, "Header repeats column(s)"),
            ("schema", 5, "missing required column(s)"),
            ("strict", 6, "strict mode is on"),
        ],
        ids=["missing-file", "empty-file", "duplicate-header", "schema-mismatch",
             "strict-rejected"],
    )
    def test_each_failure_type_has_its_own_exit_code(
        self, write_csv: WriteCsv, tmp_path: Path, capsys: pytest.CaptureFixture[str],
        setup: str, exit_code: int, message: str,
    ) -> None:
        # Functions, so only the selected case writes its file. (Building all
        # lists eagerly made every case overwrite the same tickets.csv.)
        builders: dict[str, Callable[[], list[str]]] = {
            "missing": lambda: ["--input", str(tmp_path / "nope.csv")],
            "empty": lambda: ["--input", str(write_csv(header=None))],
            "duplicate-header": lambda: ["--input", str(write_csv("T1", header="id, ID"))],
            "schema": lambda: ["--input", str(write_csv("T001", header="id"))],
            "strict": lambda: [
                "--input", str(write_csv(*VALID_ROWS, *BAD_ROWS)), "--strict",
            ],
        }
        args = builders[setup]()

        assert main(args) == exit_code
        out, err = capsys.readouterr()
        assert "ERROR: " in err and message in err
        assert out == ""                     # nothing half-printed on failure
        assert "Traceback" not in err        # expected failures are not crashes

    def test_strict_mode_error_lists_rows_even_with_logging_off(
        self, write_csv: WriteCsv, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Regression: the strict-mode message once relied on WARNING logs to
        show which rows failed; with --log-level ERROR nothing was listed."""
        path = write_csv(*VALID_ROWS, *BAD_ROWS)
        assert main(["--input", str(path), "--strict", "--log-level", "ERROR"]) == 6
        err = capsys.readouterr().err
        assert "WARNING" not in err
        assert "line 5: 'priority'" in err and "line 6: 'id' duplicates line 2" in err

    def test_invalid_log_level_from_environment_exits_2(
        self, sample_csv: Path, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv("TICKET_PIPELINE_LOG_LEVEL", "LOUD")
        assert main(["--input", str(sample_csv)]) == 2
        assert "Unknown log level 'LOUD'" in capsys.readouterr().err

    def test_unknown_cli_option_is_a_usage_error(self) -> None:
        with pytest.raises(SystemExit) as info:
            main(["--colour"])
        assert info.value.code == 2

    def test_unexpected_bug_is_not_hidden(
        self, sample_csv: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Only TicketPipelineError is handled; a programming error must
        surface with its traceback instead of being turned into an exit code."""

        def buggy(_config: PipelineConfig) -> None:
            raise ZeroDivisionError("simulated bug")

        monkeypatch.setattr("ticket_pipeline.cli.run_pipeline", buggy)
        with pytest.raises(ZeroDivisionError, match="simulated bug"):
            main(["--input", str(sample_csv)])


def test_installed_package_runs_as_a_module(sample_csv: Path) -> None:
    """Smoke test of the installed package in a separate process."""
    completed = subprocess.run(
        [sys.executable, "-m", "ticket_pipeline", "--input", str(sample_csv),
         "--log-level", "ERROR"],
        capture_output=True, text=True, timeout=60, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Rows read: 3 | valid: 3 | rejected: 0" in completed.stdout


def test_duplicate_of_a_rejected_row_is_still_reported(write_csv: WriteCsv) -> None:
    """Regression: the earlier copy is invalid, but the clash must still be
    reported, otherwise it reappears as soon as the earlier row is fixed."""
    path = write_csv(
        "T001,Ann Lee,low,billing,closed,Login issue,inf,,2024-01-15",  # line 2: bad hours
        "t001,Cy Doe,low,billing,open,Bug,,,2024-01-17",               # line 3: same ID
    )
    result = run_pipeline(PipelineConfig(input_path=path))
    assert result.tickets == ()
    assert [(e.line, e.columns) for e in result.rejected] == [
        (2, ("resolution_time_hours",)), (3, ("id",)),
    ]


def test_duplicate_row_with_other_problems_reports_everything(write_csv: WriteCsv) -> None:
    path = write_csv(*VALID_ROWS, "T002,Zed Ray,critical,billing,open,Dup,,,2024-01-17")
    result = run_pipeline(PipelineConfig(input_path=path))
    error = result.rejected[0]
    assert error.columns == ("priority", "id")
    assert isinstance(error.__cause__, ValueError)  # root cause kept when combining


def test_rows_with_empty_ids_are_not_treated_as_duplicates(write_csv: WriteCsv) -> None:
    path = write_csv(",Ann Lee,low,billing,open,A,,,2024-01-15",
                     " ,Bo Li,low,billing,open,B,,,2024-01-16")
    result = run_pipeline(PipelineConfig(input_path=path))
    assert [(e.line, e.columns) for e in result.rejected] == [(2, ("id",)), (3, ("id",))]
    assert all("required" in str(e) for e in result.rejected)
