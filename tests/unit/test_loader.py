"""Unit tests: CSVLoader file-level checks and lazy reading."""

from __future__ import annotations

from pathlib import Path

import pytest

from sample_data import HEADER, WriteCsv
from ticket_pipeline.errors import InputPathError, MalformedFileError, SchemaMismatchError
from ticket_pipeline.processing.loader import CSVLoader, RawRow
from ticket_pipeline.processing.parser import REQUIRED_COLUMNS


def test_rows_are_returned_with_physical_line_numbers(write_csv: WriteCsv) -> None:
    row = "TKT-0001,a@b.co,low,open,x,2026-10-01,"
    path = write_csv(row, "", row)
    rows = CSVLoader(path).load()
    assert [row.line for row in rows] == [2, 4]  # the blank line 3 is skipped
    assert rows[0].values["ticket_id"] == "TKT-0001"


def test_line_numbers_stay_correct_after_multiline_quoted_field(write_csv: WriteCsv) -> None:
    path = write_csv('a,"two\nlines"', "b,c", header="x,y")
    assert [row.line for row in CSVLoader(path).load()] == [3, 4]


def test_iter_rows_is_lazy(sample_csv: Path) -> None:
    rows = CSVLoader(sample_csv).iter_rows()
    first = next(rows)
    assert isinstance(first, RawRow) and first.line == 2
    rows.close()  # stopping early closes the file via the with-block


def test_header_is_normalised_and_bom_removed(write_csv: WriteCsv) -> None:
    path = write_csv("1,2", header=" ID ,Name", encoding="utf-8-sig")
    assert CSVLoader(path).load()[0].values == {"id": "1", "name": "2"}


def test_short_row_is_padded_with_empty_strings(write_csv: WriteCsv) -> None:
    path = write_csv("1", header="a,b,c")
    assert CSVLoader(path).load()[0].values == {"a": "1", "b": "", "c": ""}


def test_header_only_file_has_no_rows(write_csv: WriteCsv) -> None:
    assert CSVLoader(write_csv()).load() == []


@pytest.mark.parametrize(
    ("name", "problem"),
    [
        ("missing.csv", "not found"),
        ("data", "not a file"),
        ("tickets.txt", "Unsupported file type"),
    ],
    ids=["missing", "directory", "wrong-extension"],
)
def test_bad_path_raises_input_path_error(tmp_path: Path, name: str, problem: str) -> None:
    target = tmp_path / name
    if name == "data":
        target.mkdir()
    elif name.endswith(".txt"):
        target.write_text(HEADER)
    with pytest.raises(InputPathError, match=problem) as info:
        CSVLoader(target)
    assert info.value.path == target
    assert info.value.exit_code == 3


@pytest.mark.parametrize(
    ("rows", "header", "encoding", "problem", "line"),
    [
        ((), None, "utf-8", "File is empty", None),
        (("1,2,3",), "a,b", "utf-8", "3 fields but the header defines 2", 2),
        (("1,2",), "a,", "utf-8", "blank column name", 1),
        (("1,2",), "a,A", "utf-8", "repeats column(s): a", 1),
        (("1,José",), "a,b", "cp1252", "not valid UTF-8", None),
    ],
    ids=["empty-file", "surplus-field", "blank-header", "duplicate-header", "not-utf8"],
)
def test_malformed_file_raises_specific_error(
    write_csv: WriteCsv,
    rows: tuple[str, ...],
    header: str | None,
    encoding: str,
    problem: str,
    line: int | None,
) -> None:
    path = write_csv(*rows, header=header, encoding=encoding)
    with pytest.raises(MalformedFileError) as info:
        CSVLoader(path).load()
    assert problem in str(info.value)
    assert info.value.line == line
    assert info.value.exit_code == 4


def test_encoding_error_keeps_root_cause(write_csv: WriteCsv) -> None:
    path = write_csv("1,José", header="a,b", encoding="cp1252")
    with pytest.raises(MalformedFileError) as info:
        CSVLoader(path).load()
    assert isinstance(info.value.__cause__, UnicodeDecodeError)


def test_surplus_field_error_does_not_echo_values(write_csv: WriteCsv) -> None:
    path = write_csv("1,2,secret@example.com", header="a,b")
    with pytest.raises(MalformedFileError) as info:
        CSVLoader(path).load()
    assert "secret@example.com" not in str(info.value)


def test_missing_required_columns_raise_schema_mismatch(write_csv: WriteCsv) -> None:
    path = write_csv("TKT-0001,high", header="ticket_id,priority")
    with pytest.raises(SchemaMismatchError) as info:
        CSVLoader(path, required_columns=REQUIRED_COLUMNS).load()
    assert info.value.missing == ("category", "created_at", "customer_email", "status")
    assert info.value.found == ("ticket_id", "priority")
    assert info.value.exit_code == 5


def test_permission_error_is_translated(
    sample_csv: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The operating system is an external boundary, so it is mocked here."""

    def deny(*_args: object, **_kwargs: object) -> None:
        raise PermissionError("access denied")

    monkeypatch.setattr(Path, "open", deny)
    with pytest.raises(InputPathError, match="Permission denied") as info:
        CSVLoader(sample_csv).load()
    assert isinstance(info.value.__cause__, PermissionError)
