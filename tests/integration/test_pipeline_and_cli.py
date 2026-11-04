"""
Integration tests: the real loader, parser, pipeline and CLI working together
on real temporary files. Nothing internal is mocked.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from sample_data import VALID_ROWS, WriteCsv
from ticket_pipeline.cli import main
from ticket_pipeline.config import DEFAULT_INPUT_PATH, PipelineConfig
from ticket_pipeline.errors import RejectedRowsError
from ticket_pipeline.pipeline import run_pipeline

pytestmark = pytest.mark.integration

BAD_ROWS = (
    "TKT-0004,dana@example.com,critical,open,billing,2026-10-02,",  # line 5: priority
    "TKT-0001,eve@example.com,low,open,billing,2026-10-02,",        # line 6: duplicate
)


def test_valid_file_produces_tickets_and_summary(sample_csv: Path) -> None:
    result = run_pipeline(PipelineConfig(input_path=sample_csv))
    assert result.rows_read == 3
    assert [t.ticket_id for t in result.tickets] == ["TKT-0001", "TKT-0002", "TKT-0003"]
    assert result.rejected == ()
    assert result.summary.mean_resolution_hours == 6.0


def test_bad_rows_are_rejected_but_good_rows_kept(write_csv: WriteCsv) -> None:
    result = run_pipeline(PipelineConfig(input_path=write_csv(*VALID_ROWS, *BAD_ROWS)))
    assert len(result.tickets) == 3
    assert [(e.line, e.column) for e in result.rejected] == [(5, "priority"), (6, "ticket_id")]
    assert "duplicate of line 2" in str(result.rejected[1])


def test_strict_mode_fails_when_rows_are_rejected(write_csv: WriteCsv) -> None:
    path = write_csv(*VALID_ROWS, *BAD_ROWS)
    with pytest.raises(RejectedRowsError, match="2 of 5 row") as info:
        run_pipeline(PipelineConfig(input_path=path, strict=True))
    assert [(e.line, e.column) for e in info.value.rejected] == [(5, "priority"), (6, "ticket_id")]


def test_strict_mode_error_lists_rows_even_with_logging_off(
    write_csv: WriteCsv, capsys: pytest.CaptureFixture[str]
) -> None:
    """Regression: the strict-mode message once said 'rows listed above', but
    with --log-level ERROR nothing was listed. The rows are now in the error."""
    path = write_csv(*VALID_ROWS, *BAD_ROWS)
    assert main(["--input", str(path), "--strict", "--log-level", "ERROR"]) == 6
    err = capsys.readouterr().err
    assert "WARNING" not in err
    assert "line 5, column 'priority'" in err
    assert "line 6, column 'ticket_id': duplicate of line 2" in err


def test_logs_describe_stages_without_personal_data(
    write_csv: WriteCsv, caplog: pytest.LogCaptureFixture
) -> None:
    path = write_csv(*VALID_ROWS, *BAD_ROWS)
    with caplog.at_level(logging.DEBUG, logger="ticket_pipeline"):
        run_pipeline(PipelineConfig(input_path=path))
    assert "stage=load status=started file=tickets.csv" in caplog.text
    assert "status=rejected line=5 column=priority" in caplog.text
    assert "rows=5 valid=3 rejected=2" in caplog.text
    assert "stage=pipeline outcome=completed" in caplog.text
    assert "@example.com" not in caplog.text          # no e-mail addresses
    assert str(path.parent) not in caplog.text        # no full file-system paths


def test_header_only_file_logs_warning(
    write_csv: WriteCsv, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="ticket_pipeline"):
        result = run_pipeline(PipelineConfig(input_path=write_csv()))
    assert result.rows_read == 0
    assert "status=empty" in caplog.text


class TestCommandLine:
    def test_success_prints_report_to_stdout(
        self, sample_csv: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["--input", str(sample_csv)]) == 0
        out, err = capsys.readouterr()
        assert "Rows read: 3 | valid: 3 | rejected: 0" in out
        assert "stage=load" in err          # logs go to stderr, not stdout
        assert "stage=load" not in out

    def test_rejected_rows_are_listed_without_email(
        self, write_csv: WriteCsv, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["--input", str(write_csv(*VALID_ROWS, *BAD_ROWS))]) == 0
        out, err = capsys.readouterr()
        assert "line 5, column 'priority'" in out
        assert "@example.com" not in out + err

    @pytest.mark.parametrize(
        ("setup", "exit_code", "message"),
        [
            ("missing", 3, "Input file not found"),
            ("empty", 4, "File is empty"),
            ("schema", 5, "missing required column(s)"),
            ("strict", 6, "strict mode is on"),
        ],
        ids=["missing-file", "empty-file", "schema-mismatch", "strict-rejected"],
    )
    def test_each_failure_type_has_its_own_exit_code(
        self,
        write_csv: WriteCsv,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        setup: str,
        exit_code: int,
        message: str,
    ) -> None:
        args: list[str]
        if setup == "missing":
            args = ["--input", str(tmp_path / "nope.csv")]
        elif setup == "empty":
            args = ["--input", str(write_csv(header=None))]
        elif setup == "schema":
            args = ["--input", str(write_csv("TKT-0001", header="ticket_id"))]
        else:
            args = ["--input", str(write_csv(*VALID_ROWS, *BAD_ROWS)), "--strict"]

        assert main(args) == exit_code
        out, err = capsys.readouterr()
        assert "ERROR: " in err and message in err
        assert out == ""                     # nothing half-printed on failure
        assert "Traceback" not in err        # expected failures are not crashes

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

    def test_bundled_sample_file_runs(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert DEFAULT_INPUT_PATH.exists()
        assert main([]) == 0
        assert "Rows read: 12 | valid: 6 | rejected: 6" in capsys.readouterr().out


def test_unexpected_bug_is_not_hidden(
    sample_csv: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only TicketPipelineError is handled; a programming error must surface
    with its traceback instead of being turned into an exit code."""

    def buggy(_config: PipelineConfig) -> None:
        raise ZeroDivisionError("simulated bug")

    monkeypatch.setattr("ticket_pipeline.cli.run_pipeline", buggy)
    with pytest.raises(ZeroDivisionError, match="simulated bug"):
        main(["--input", str(sample_csv)])
