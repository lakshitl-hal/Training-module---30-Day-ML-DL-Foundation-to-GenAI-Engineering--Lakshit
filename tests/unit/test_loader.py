"""Unit tests: CSVLoader file-level checks and lazy reading."""

from __future__ import annotations

from pathlib import Path

import pytest

from sample_data import HEADER, WriteCsv
from ticket_pipeline.errors import InputPathError, MalformedFileError, SchemaMismatchError
from ticket_pipeline.processing.loader import CSVLoader, RawRow
from ticket_pipeline.processing.parser import REQUIRED_COLUMNS


def test_rows_carry_physical_line_numbers(write_csv: WriteCsv) -> None:
    path = write_csv("1,x", "", "2,y", header="a,b")
    assert [row.line for row in CSVLoader(path).load()] == [2, 4]  # blank line 3 skipped


def test_line_number_is_where_a_multiline_row_starts(write_csv: WriteCsv) -> None:
    """Regression: a quoted value spanning lines 2-3 must be reported as line 2."""
    path = write_csv('1,"two\nlines"', "2,y", header="a,b")
    rows = CSVLoader(path).load()
    assert [row.line for row in rows] == [2, 4]
    assert rows[0].values["b"] == "two\nlines"


def test_whitespace_only_lines_are_skipped(write_csv: WriteCsv) -> None:
    path = write_csv("   ", " , ", "1,x", header="a,b")
    assert [row.line for row in CSVLoader(path).load()] == [4]


def test_iter_rows_is_lazy(sample_csv: Path) -> None:
    rows = CSVLoader(sample_csv).iter_rows()
    first = next(rows)
    assert isinstance(first, RawRow) and first.line == 2
    rows.close()  # stopping early closes the file through the with-block


def test_header_is_normalised_and_bom_removed(write_csv: WriteCsv) -> None:
    path = write_csv("1,2", header=" ID ,Customer", encoding="utf-8-sig")
    assert CSVLoader(path).load()[0].values == {"id": "1", "customer": "2"}


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


def test_uppercase_extension_is_accepted(write_csv: WriteCsv) -> None:
    assert CSVLoader(write_csv("1", header="a", name="TICKETS.CSV")).load()[0].values == {"a": "1"}


@pytest.mark.parametrize(
    ("header", "variant"),
    [
        pytest.param("id,customer,id", "'id', 'id'", id="exact-duplicate"),
        pytest.param("id,customer,ID", "'id', 'ID'", id="case-variant"),
        pytest.param("id,customer, id ", "'id', ' id '", id="whitespace-variant"),
        pytest.param("id,customer, Id", "'id', ' Id'", id="case-and-whitespace"),
    ],
)
def test_duplicate_columns_after_normalisation_are_rejected(
    write_csv: WriteCsv, header: str, variant: str
) -> None:
    """Regression: two header cells that normalise to the same name would
    silently overwrite each other's values, so the file is rejected."""
    path = write_csv("T1,Alice,T2", header=header)
    with pytest.raises(MalformedFileError) as info:
        CSVLoader(path).load()
    assert f"'id' appears as {variant}" in str(info.value)
    assert info.value.line == 1


@pytest.mark.parametrize(
    ("rows", "header", "encoding", "problem", "line"),
    [
        ((), None, "utf-8", "File is empty", None),
        (("1,2,3",), "a,b", "utf-8", "3 fields but the header defines 2", 2),
        (("1,2",), "a,", "utf-8", "blank column name", 1),
        (("1,José",), "a,b", "cp1252", "not valid UTF-8", None),
        (("1,ok", '2,"unterminated', "3,z"), "a,b", "utf-8", "unexpected end of data", 3),
        (('1,"x"y',), "a,b", "utf-8", "could not be parsed", 2),
        (("1,B\x00ob",), "a,b", "utf-8", "NUL byte", 2),
        (("1," + "x" * 140_000,), "a,b", "utf-8", "field larger than field limit", 2),
    ],
    ids=[
        "empty-file", "surplus-field", "blank-header", "not-utf8",
        "unbalanced-quote", "stray-quote", "nul-byte", "oversized-field",
    ],
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
    path = write_csv("1,2,Secret Person", header="a,b")
    with pytest.raises(MalformedFileError) as info:
        CSVLoader(path).load()
    assert "Secret Person" not in str(info.value)


def test_missing_required_columns_raise_schema_mismatch(write_csv: WriteCsv) -> None:
    path = write_csv("T001,high", header="id,priority")
    with pytest.raises(SchemaMismatchError) as info:
        CSVLoader(path, required_columns=REQUIRED_COLUMNS).load()
    assert info.value.missing == ("category", "created_at", "customer", "description", "status")
    assert info.value.found == ("id", "priority")
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


def test_repr_shows_file_name_not_full_path(sample_csv: Path) -> None:
    text = repr(CSVLoader(sample_csv))
    assert text == "CSVLoader(path='tickets.csv')"
    assert str(sample_csv.parent) not in text
