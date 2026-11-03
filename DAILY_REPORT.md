# Daily Engineering Report — Day 02

| Field | Value |
|---|---|
| **Programme** | 30-Day ML/DL Foundation to GenAI Engineering |
| **Module** | Day 02 — Object-Oriented Python & Reusable Modules |
| **Developer** | Lakshit (HALCER) |
| **Date** | 03 November 2026 |
| **Duration** | 8 hours (4 hours study + 4 hours implementation) |
| **Status** | Complete |
| **Test Result** | 122 passed, 0 failed |

---

## 1. Study Summary

### 1.1 Classes and Object Model (60 min)

The session covered the Python object lifecycle, the role of `self`, and the difference between construction (`__init__`) and post-construction validation (`__post_init__` in dataclasses).

**Key learnings:**

- `self` is explicitly passed as the first argument to every instance method. Python binds it automatically at call time; it is not a keyword but a strong convention.
- `__init__` initialises state; `__post_init__` in a `@dataclass` class runs after the auto-generated `__init__` completes, making it the correct place to validate fields whose values depend on each other.
- **Instance attributes** (e.g., `self._path`) are unique to each object. **Class attributes** (e.g., `SUPPORTED_EXTENSIONS`) are shared across all instances and should be used for configuration constants and lookup tables.
- The full lifecycle is: `__new__` allocates memory → `__init__` initialises state → `__del__` releases resources (rarely required in application code).

---

### 1.2 OOP Design Principles (60 min)

The session focused on the four pillars — encapsulation, inheritance, composition, and polymorphism — with emphasis on when **not** to use inheritance.

**Key learnings:**

- **Single Responsibility Principle (SRP):** A class should have exactly one reason to change. A class that loads, validates, cleans, and analyses data in a single body is called a *God Object*. It cannot be tested in isolation and breaks across multiple axes of change.
- **Encapsulation:** Private methods are prefixed with `_`. This is a convention, not an enforcement, but it communicates a clear contract: methods beginning with `_` are implementation details and are not part of the public API.
- **Composition over Inheritance:** Inheritance models an *is-a* relationship. When no such relationship exists — for example, an analytics engine is not a type of ticket — composition is correct. `AnalyticsEngine` receives tickets as data; it does not extend a ticket class.
- **Polymorphism via Enum:** Replacing raw string comparisons (`priority == "high"`) with typed Enum values (`priority == Priority.HIGH`) eliminates an entire class of case-sensitivity and typo bugs.

---

### 1.3 Python Data Model (60 min)

The session covered magic methods, properties, and the `@dataclass` decorator as a productivity and correctness tool.

**Key learnings:**

- `@dataclass` auto-generates `__init__`, `__repr__`, and `__eq__` from field annotations, eliminating boilerplate while keeping behaviour predictable.
- `@property` exposes computed values without storing redundant state. `is_open` and `is_high_priority` are derived from `status` and `priority` respectively; storing them separately would create a synchronisation problem.
- `__str__` is the human-readable representation (used in `print()`, log messages, and UI). `__repr__` is the unambiguous developer representation (used in REPLs, debuggers, and test failure output). Both should be implemented.
- `class Priority(str, Enum)` inherits from both `str` and `Enum`. The `str` mixin means `Priority.HIGH == "high"` evaluates to `True`, which makes Enum values transparent in comparisons and JSON serialisation.

---

### 1.4 Design Review (60 min)

The session examined a deliberately problematic monolithic class and identified the violations it contains.

**Key learnings:**

- **Cohesion** measures how closely related the methods of a class are. A class whose methods all operate on the same concept has high cohesion; one where methods address unrelated concerns has low cohesion.
- **Coupling** measures how much one class depends on the internals of another. Classes should communicate through defined interfaces — lists, dataclasses, return values — not through shared mutable state.
- **Testability** is a consequence of good design. A class with no side effects, which accepts its dependencies as constructor arguments and returns values rather than printing them, is inherently easy to unit test.
- A class performing load + validate + clean + analyse in a single body is both a God Object (SRP violation) and a testing liability — any test must exercise all four concerns simultaneously.

---

## 2. Implementation Log

### 2.1 Deliverables

| Task | Deliverable | Outcome |
|---|---|---|
| **Task A — Domain Model** | `SupportTicket` dataclass with `Priority`, `Status`, `Category` Enums; `__post_init__` invariant enforcement | Complete |
| **Task B — Separated Responsibilities** | `CSVLoader`, `TicketValidator`, `DataCleaner` in isolated modules; no shared mutable state | Complete |
| **Task C — Extended Analytics** | `AnalyticsEngine.top_customers()` and `daily_volume()` added without modifying any existing method | Complete |
| **Task D — Tests and Documentation** | 122 automated tests across 6 files; `README.md`; `DAILY_REPORT.md` | Complete |

### 2.2 Artefact Inventory

| File | Purpose | Lines |
|---|---|---|
| `src/models/ticket.py` | Domain model and Enum types | ~80 |
| `src/io/loader.py` | CSV file reader with field-count integrity | ~75 |
| `src/validation/validator.py` | Business rule enforcement per row | ~96 |
| `src/processing/cleaner.py` | Value normalisation and canonicalisation | ~75 |
| `src/analytics/engine.py` | Metrics, filters, and reporting | ~95 |
| `tests/test_ticket.py` | 12 tests for domain model | — |
| `tests/test_loader.py` | 9 tests for CSV loading and integrity | — |
| `tests/test_validator.py` | 16 tests for validation rules | — |
| `tests/test_cleaner.py` | 13 tests for normalisation | — |
| `tests/test_analytics.py` | 17 tests for analytics operations | — |
| `main.py` | End-to-end pipeline demonstration | ~55 |
| `data/tickets.csv` | Sample dataset (10 rows, 3 invalid) | — |

---

## 3. Issues Encountered

### Issue 1 — Enum Case Sensitivity in Validation

**Context:** `TicketValidator` checks priority values against a set of valid strings. The CSV data may contain values such as `"URGENT"` or `"High"` in mixed case.

**Problem:** The initial implementation compared the raw string directly against the set `{"low", "medium", "high", "urgent"}`. The comparison `"URGENT" in VALID_PRIORITIES` evaluates to `False` because the set contains only lowercase values. This caused valid tickets with non-lowercase priority strings to be incorrectly rejected.

**Resolution:** All input strings are normalised with `.strip().lower()` before set membership is checked. The validator now accepts any casing of a valid priority value. A dedicated test (`test_uppercase_priority_is_accepted`) documents this behaviour explicitly.

---

### Issue 2 — Dataclass Field with Default Value

**Context:** `SupportTicket` defines a constant `MAX_DESCRIPTION_LENGTH` to cap description length during validation.

**Problem:** Declaring `MAX_DESCRIPTION_LENGTH: int = 500` as a plain dataclass field caused Python to raise `TypeError` at class definition time. In a dataclass, fields with defaults must follow fields without defaults — this constant was interfering with the field ordering constraint.

**Resolution:** The constant was declared using `field(default=500, init=False, repr=False, compare=False)`. The `init=False` argument excludes it from the auto-generated constructor; `repr=False` and `compare=False` exclude it from `__repr__` and `__eq__`. This informs the dataclass machinery that the constant is not a data field.

---

### Issue 3 — DataCleaner Mutating Caller Input

**Context:** `DataCleaner._clean_row` receives a dictionary and applies normalisation transformations.

**Problem:** The initial implementation modified the dictionary in place (e.g., `row["priority"] = ...`). Because Python dicts are passed by reference, this mutated the caller's original data. The test `test_does_not_mutate_original` failed because the original row was changed after `clean_all` returned.

**Resolution:** `_clean_row` begins with `row = {k: v.strip() for k, v in row.items()}`, which creates a new dictionary from the input. All subsequent modifications are applied to the copy. The original is never touched.

---

### Issue 4 — Architectural Risk: Circular Import

**Context:** `DataCleaner` in `src/processing/cleaner.py` imports Enum types from `src/models/ticket.py`.

**Problem:** This import direction is correct. However, a future developer could introduce an import in the reverse direction — for example, importing `DataCleaner` inside `ticket.py`. This would create a circular import and crash the interpreter with an `ImportError` at startup.

**Resolution:** The dependency direction is enforced architecturally: `models/` is the innermost layer and must never import from `processing/`, `validation/`, `io/`, or `analytics/`. Outer layers depend on inner layers; the reverse is forbidden. No code change was required; this is a documented constraint on future changes.

---

### Issue 5 — Silent Column Corruption on Malformed CSV

**Context:** `CSVLoader` uses Python's `csv.DictReader` to parse CSV files. The standard library's `DictReader` is permissive by default.

**Problem:** When a data row contains more fields than the header defines, `DictReader` places the surplus values under the dictionary key `None`. This does not raise an exception. All downstream components then receive a row where `row["id"]` contains the category value, `row["category"]` contains the priority value, and so on. The data corruption is silent and not detectable by `TicketValidator` because the field names are still present — only their values are wrong.

**Resolution:** After yielding each row from `DictReader`, the loader checks whether the key `None` is present in the row dictionary. If it is, a `ValueError` is raised immediately with the row number, the expected field count, and the surplus values. Five regression tests were added to cover this scenario, including the exact reproducer pattern (a row with one extra field appended after the final column).

---

## 4. Bugs Found and Resolved

| # | Severity | Description | Root Cause | Resolution |
|---|---|---|---|---|
| 1 | Medium | `TicketValidator` incorrectly rejected `"URGENT"` (uppercase) as an invalid priority | Case-sensitive set membership check | Applied `.lower()` normalisation before set lookup |
| 2 | Medium | `DataCleaner` mutated the caller's input dictionary | In-place dict modification via key assignment | Created a copy at the start of `_clean_row` using a dict comprehension |
| 3 | Medium | `SupportTicket` accepted whitespace-only strings (e.g., `"   "`) for required fields | Validation checked `if not value` — an empty-after-strip string is truthy before stripping | Changed to `if not value.strip()` throughout `__post_init__` |
| 4 | Low | `AnalyticsEngine.open_tickets()` undercounted — `PENDING` tickets were excluded | `is_open` property only checked `Status.OPEN` | Updated `is_open` to return `True` for both `Status.OPEN` and `Status.PENDING` |
| 5 | Critical | Malformed CSV rows silently corrupted ticket identifiers and field values | `csv.DictReader` places surplus fields under key `None`, shifting all column assignments | Added `None`-key detection in `CSVLoader._iter_rows` with an immediate `ValueError` |
| 6 | Critical | `inf`/`nan` durations and fractional ratings were accepted; they poisoned averages (code review B1) | `float('inf')` parses successfully and `nan` fails every comparison, so range checks never fired; the model did not validate numeric fields at all | Added `math.isfinite`, type and range checks in `SupportTicket` and `TicketValidator`; regression tests for +inf, -inf, nan, 3.5, bool |
| 7 | High | Truncated CSV rows crashed the pipeline with `AttributeError` | `csv.DictReader` fills missing cells with `None`, and `None.strip()` fails | Loader pads with `""`, cleaner/validator are None-safe; `test_pipeline.py` covers loader → model |
| 8 | Low | `MAX_DESCRIPTION_LENGTH` was a per-instance dataclass field; model claimed immutability but was not frozen | Misuse of `field(init=False)` for a constant | Now `ClassVar`, and `@dataclass(frozen=True)` |

---

## 5. Test Execution Evidence

```
$ python -m pytest -q
122 passed
```

Full verbose output: `logs/test_results.txt`. Pipeline output: `logs/pipeline_output.txt`.

---

## 6. Key Takeaways

| Principle | Applied Practice |
|---|---|
| A class should have one reason to change | Five classes, five concerns — no method belongs to more than one class |
| An object must never exist in an invalid state | `SupportTicket.__post_init__` raises `ValueError` before construction completes if any invariant is violated |
| Prefer composition when no is-a relationship exists | `AnalyticsEngine` receives tickets; it does not extend a ticket-related class |
| Input must never be mutated by a processing stage | `DataCleaner` copies the input dictionary before modifying it |
| Silent data corruption is worse than an explicit failure | `CSVLoader` raises immediately on malformed rows rather than returning shifted column values |
| Tests are easiest to write when each class does exactly one thing | Nearly all of the 122 tests exercise a single class; only `test_pipeline.py` deliberately checks the stages together |

---

*End of Report*
