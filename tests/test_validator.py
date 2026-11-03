"""Tests for TicketValidator."""

import pytest
from src.validation.validator import TicketValidator, ValidationResult


def _make_row(**overrides) -> dict:
    base = {
        "id": "T001",
        "customer": "Alice",
        "priority": "high",
        "category": "billing",
        "status": "open",
        "description": "Some issue",
        "created_at": "2024-01-15",
    }
    base.update(overrides)
    return base


class TestTicketValidator:
    def setup_method(self):
        self.validator = TicketValidator()

    def test_valid_row_passes(self):
        result = self.validator.validate_all([_make_row()])[0]
        assert result.is_valid is True

    def test_missing_customer_fails(self):
        result = self.validator.validate_all([_make_row(customer="")])[0]
        assert result.is_valid is False
        assert any("customer" in e for e in result.errors)

    def test_invalid_priority_fails(self):
        # Validator lowercases before checking, so "URGENT" -> "urgent" is valid.
        # Test that a genuinely unknown priority string fails instead.
        result = self.validator.validate_all([_make_row(priority="critical")])[0]
        assert result.is_valid is False
        assert any("priority" in e for e in result.errors)

    def test_uppercase_priority_is_accepted(self):
        # "URGENT" uppercased is normalised to "urgent" by the validator,
        # so it should pass validation (not raise an error).
        result = self.validator.validate_all([_make_row(priority="URGENT")])[0]
        assert result.is_valid is True

    def test_invalid_status_fails(self):
        result = self.validator.validate_all([_make_row(status="unknown")])[0]
        assert result.is_valid is False

    def test_filter_valid_removes_bad_rows(self):
        rows = [_make_row(), _make_row(customer="")]
        valid = self.validator.filter_valid(rows)
        assert len(valid) == 1

    def test_validation_result_str_ok(self):
        r = ValidationResult(row_index=1, is_valid=True)
        assert "OK" in str(r)

    def test_validation_result_str_invalid(self):
        r = ValidationResult(row_index=2, is_valid=False, errors=["missing 'id'"])
        assert "INVALID" in str(r)

    # ------------------------------------------------------------------
    # Additional edge-case tests
    # ------------------------------------------------------------------

    def test_missing_id_fails(self):
        result = self.validator.validate_all([_make_row(id="")])[0]
        assert result.is_valid is False
        assert any("id" in e for e in result.errors)

    def test_missing_description_fails(self):
        result = self.validator.validate_all([_make_row(description="")])[0]
        assert result.is_valid is False
        assert any("description" in e for e in result.errors)

    def test_whitespace_only_field_counts_as_missing(self):
        """A field containing only spaces should be treated as missing."""
        result = self.validator.validate_all([_make_row(customer="   ")])[0]
        assert result.is_valid is False

    def test_multiple_errors_reported_together(self):
        """A row missing both customer and description reports both errors."""
        result = self.validator.validate_all(
            [_make_row(customer="", description="")]
        )[0]
        assert result.is_valid is False
        assert len(result.errors) >= 2

    def test_validate_all_returns_result_per_row(self):
        rows = [_make_row(), _make_row(customer=""), _make_row()]
        results = self.validator.validate_all(rows)
        assert len(results) == 3
        assert results[0].is_valid is True
        assert results[1].is_valid is False
        assert results[2].is_valid is True

    def test_row_index_matches_position(self):
        """Row index in ValidationResult starts at 1 (human-readable)."""
        rows = [_make_row(customer="")]
        result = self.validator.validate_all(rows)[0]
        assert result.row_index == 1

    def test_all_valid_rows_kept_by_filter(self):
        rows = [_make_row(), _make_row(id="T002")]
        assert len(self.validator.filter_valid(rows)) == 2

    def test_all_invalid_rows_removed_by_filter(self):
        rows = [_make_row(customer=""), _make_row(description="")]
        assert self.validator.filter_valid(rows) == []


class TestNumericAndStructuralValidation:
    def setup_method(self):
        self.validator = TicketValidator()

    def _one(self, **kw):
        return self.validator.validate_all([_make_row(**kw)])[0]

    @pytest.mark.parametrize("bad", ["inf", "-inf", "nan", "Infinity", "1e400", "abc", "-2", "2_0"])
    def test_bad_resolution_time_rejected(self, bad):
        r = self._one(resolution_time_hours=bad)
        assert not r.is_valid
        assert any("resolution_time_hours" in e for e in r.errors)

    @pytest.mark.parametrize("good", ["", "0", "2", "4.5"])
    def test_good_resolution_time_accepted(self, good):
        assert self._one(resolution_time_hours=good).is_valid

    @pytest.mark.parametrize("bad", ["3.5", "4.0", "nan", "inf", "0", "6", "x", "1_0"])
    def test_bad_rating_rejected(self, bad):
        r = self._one(customer_rating=bad)
        assert not r.is_valid
        assert any("customer_rating" in e for e in r.errors)

    @pytest.mark.parametrize("good", ["", "1", "5"])
    def test_good_rating_accepted(self, good):
        assert self._one(customer_rating=good).is_valid

    def test_invalid_date_rejected(self):
        assert not self._one(created_at="not-a-date").is_valid

    def test_none_values_do_not_crash(self):
        row = _make_row(customer=None, description=None)
        r = self.validator.validate_all([row])[0]
        assert not r.is_valid

    def test_missing_keys_do_not_crash(self):
        assert not self.validator.validate_all([{"id": "T1"}])[0].is_valid

    def test_rules_share_source_with_model(self):
        from src.models.ticket import Priority
        from src.validation.validator import VALID_PRIORITIES
        assert VALID_PRIORITIES == {p.value for p in Priority}
