"""Tests for CSVLoader."""

import pytest
from pathlib import Path
from src.io.loader import CSVLoader


class TestCSVLoader:
    def test_load_returns_list_of_dicts(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("id,name\n1,Alice\n2,Bob\n")
        loader = CSVLoader(csv_file)
        rows = loader.load()
        assert len(rows) == 2
        assert rows[0]["name"] == "Alice"

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            CSVLoader(tmp_path / "nonexistent.csv")

    def test_wrong_extension_raises(self, tmp_path):
        txt_file = tmp_path / "data.txt"
        txt_file.write_text("id,name\n")
        with pytest.raises(ValueError, match="Unsupported file type"):
            CSVLoader(txt_file)

    def test_repr(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("id\n1\n")
        loader = CSVLoader(csv_file)
        assert "CSVLoader" in repr(loader)

    # ------------------------------------------------------------------
    # Regression: extra-field row must be REJECTED, not silently accepted
    # ------------------------------------------------------------------

    def test_extra_field_row_raises_value_error(self, tmp_path):
        """
        A row with more fields than the header must raise ValueError.

        Without this guard, csv.DictReader silently places the extra value
        under the key ``None``, which shifts all column values — the ticket
        ID becomes the category name, priorities shift into description, etc.
        The data must never be silently corrupted; rejection is the only
        safe behaviour.

        Minimal reproducer (matches the Day-1 review blocking defect):
            id,category,priority,description,status
            T-101,Billing,High,Valid,Closed,UNEXPECTED_EXTRA
            T-102,Technical,Low,Valid,Open
        """
        csv_content = (
            "id,category,priority,description,status\n"
            "T-101,Billing,High,Valid,Closed,UNEXPECTED_EXTRA\n"  # surplus field
            "T-102,Technical,Low,Valid,Open\n"
        )
        csv_file = tmp_path / "malformed.csv"
        csv_file.write_text(csv_content)
        loader = CSVLoader(csv_file)

        with pytest.raises(ValueError, match="Malformed rows must be fixed"):
            loader.load()

    def test_extra_field_error_message_includes_row_number(self, tmp_path):
        """The error message should identify which row is malformed."""
        csv_content = (
            "id,name\n"
            "1,Alice,EXTRA\n"  # row 2 (line 1 = header)
        )
        csv_file = tmp_path / "bad.csv"
        csv_file.write_text(csv_content)
        loader = CSVLoader(csv_file)

        with pytest.raises(ValueError, match="Row 2"):
            loader.load()

    def test_extra_field_error_does_not_corrupt_ticket_id(self, tmp_path):
        """
        Verify the specific corruption the reviewer described:
        ticket IDs must NOT silently become category names.
        The loader must reject rather than return corrupted data.
        """
        csv_content = (
            "id,category,priority,description,resolution_time_hours,"
            "customer_rating,status\n"
            "T-101,Billing,High,Valid,2,5,Closed,UNEXPECTED\n"
            "T-102,Technical,Low,Valid,4,4,Open\n"
        )
        csv_file = tmp_path / "corrupt.csv"
        csv_file.write_text(csv_content)
        loader = CSVLoader(csv_file)

        # Must raise — must NOT return rows where id == "Billing"
        with pytest.raises(ValueError):
            loader.load()

    def test_normal_rows_with_exact_field_count_pass(self, tmp_path):
        """Good rows with exactly the right number of fields load cleanly."""
        csv_content = (
            "id,category,priority,description,status\n"
            "T-101,Billing,High,Valid ticket,Open\n"
            "T-102,Technical,Low,Another ticket,Closed\n"
        )
        csv_file = tmp_path / "good.csv"
        csv_file.write_text(csv_content)
        loader = CSVLoader(csv_file)
        rows = loader.load()

        assert len(rows) == 2
        # IDs must be the actual ticket IDs, not shifted column values
        assert rows[0]["id"] == "T-101"
        assert rows[1]["id"] == "T-102"
        assert rows[0]["category"] == "Billing"

    def test_empty_csv_loads_zero_rows(self, tmp_path):
        """A header-only CSV with no data rows returns an empty list."""
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("id,name\n")
        loader = CSVLoader(csv_file)
        assert loader.load() == []


class TestEncodingAndHeaders:
    def test_excel_bom_is_removed(self, tmp_path):
        f = tmp_path / "bom.csv"
        f.write_bytes("id,name\n1,Alice\n".encode("utf-8-sig"))
        assert CSVLoader(f).load() == [{"id": "1", "name": "Alice"}]

    def test_header_names_are_stripped_and_lowercased(self, tmp_path):
        f = tmp_path / "h.csv"
        f.write_text(" ID , Name \n1,Alice\n")
        assert CSVLoader(f).load() == [{"id": "1", "name": "Alice"}]

    def test_non_utf8_file_raises_clear_value_error(self, tmp_path):
        f = tmp_path / "latin.csv"
        f.write_bytes("id,name\n1,José\n".encode("cp1252"))
        with pytest.raises(ValueError, match="not valid UTF-8"):
            CSVLoader(f).load()

    def test_header_only_file_returns_no_rows(self, tmp_path):
        f = tmp_path / "empty.csv"
        f.write_text("id,name\n")
        assert CSVLoader(f).load() == []
