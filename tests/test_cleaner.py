"""Tests for DataCleaner."""

from src.processing.cleaner import DataCleaner


def _make_row(**overrides) -> dict:
    base = {
        "id": "T001",
        "customer": "alice",
        "priority": "high",
        "category": "billing",
        "status": "open",
        "description": "Some issue",
        "created_at": "2024-01-15",
    }
    base.update(overrides)
    return base


class TestDataCleaner:
    def setup_method(self):
        self.cleaner = DataCleaner()

    def test_strips_whitespace(self):
        row = _make_row(id=" T001 ", customer=" Alice ", priority=" high ")
        cleaned = self.cleaner.clean_all([row])[0]
        assert cleaned["id"] == "T001"
        assert cleaned["customer"] == "Alice"

    def test_normalises_priority_to_lowercase(self):
        cleaned = self.cleaner.clean_all([_make_row(priority="HIGH")])[0]
        assert cleaned["priority"] == "high"

    def test_normalises_urgent_priority(self):
        cleaned = self.cleaner.clean_all([_make_row(priority="URGENT")])[0]
        assert cleaned["priority"] == "urgent"

    def test_unknown_category_becomes_unknown(self):
        cleaned = self.cleaner.clean_all([_make_row(category="alien_category")])[0]
        assert cleaned["category"] == "unknown"

    def test_known_category_is_preserved(self):
        for cat in ("billing", "technical", "account", "general"):
            cleaned = self.cleaner.clean_all([_make_row(category=cat)])[0]
            assert cleaned["category"] == cat

    def test_does_not_mutate_original(self):
        row = _make_row(customer="bob")
        original_customer = row["customer"]
        self.cleaner.clean_all([row])
        # Original dict must be unchanged
        assert row["customer"] == original_customer

    def test_customer_name_is_title_cased(self):
        cleaned = self.cleaner.clean_all([_make_row(customer="alice johnson")])[0]
        assert cleaned["customer"] == "Alice Johnson"

    def test_all_statuses_normalised(self):
        for status in ("open", "pending", "resolved", "closed"):
            cleaned = self.cleaner.clean_all([_make_row(status=status.upper())])[0]
            assert cleaned["status"] == status

    def test_unknown_status_defaults_to_open(self):
        cleaned = self.cleaner.clean_all([_make_row(status="weird_status")])[0]
        assert cleaned["status"] == "open"

    def test_unknown_priority_defaults_to_low(self):
        cleaned = self.cleaner.clean_all([_make_row(priority="critical")])[0]
        assert cleaned["priority"] == "low"

    def test_clean_all_returns_same_count(self):
        rows = [_make_row(), _make_row(id="T002"), _make_row(id="T003")]
        cleaned = self.cleaner.clean_all(rows)
        assert len(cleaned) == 3

    def test_empty_list_returns_empty_list(self):
        assert self.cleaner.clean_all([]) == []

    def test_repr(self):
        assert repr(self.cleaner) == "DataCleaner()"
