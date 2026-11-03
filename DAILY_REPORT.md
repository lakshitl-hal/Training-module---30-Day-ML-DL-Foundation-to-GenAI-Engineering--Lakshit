# Daily Report — Day 02

| Field | Value |
|---|---|
| **Programme** | 30-Day ML/DL Foundation to GenAI Engineering |
| **Module** | Day 02 — Object-Oriented Python & Reusable Modules |
| **Developer** | Lakshit (HALCER) |
| **Date** | 03 November 2026 |
| **Duration** | 8 hours — 4 hours study + 4 hours implementation |
| **Status** | Implementation complete; ready for code review |
| **Test result** | 140 passed, 0 failed (`logs/test_results.txt`) |

---

## 1. Topics Learned

| Study block | Topics | Required output — how it was produced |
|---|---|---|
| Classes and object model (60 min) | Instances, attributes, methods, constructors, `self`, object lifecycle | Implemented `CSVLoader`, `TicketValidator`, `DataCleaner`, `AnalyticsEngine`; instance state documented in each class docstring |
| OOP design (60 min) | Encapsulation, inheritance, composition, polymorphism, interfaces | Compared a single-class design with a composed design and chose composition (README §9.1) |
| Python data model (60 min) | Class vs instance attributes, properties, `__repr__` / `__str__`, dataclasses, `ClassVar`, frozen dataclasses | `SupportTicket` is a frozen dataclass with `ClassVar` constants, properties and a readable `__str__` |
| Design review (60 min) | Single responsibility, dependency boundaries, cohesion, coupling, testability | Review of a monolithic ticket class (Section 1.1 below) and adversarial review of my own code (Section 5) |

### 1.1 Design review exercise — monolithic ticket class

The exercise reviewed a `TicketProcessor` class that read the CSV file, validated rows, cleaned them, built tickets and printed statistics in one class.

| Issue identified | Why it is a problem | How the refactor addresses it |
|---|---|---|
| Four responsibilities in one class (god object) | Four unrelated reasons to change; a change to file reading can break analytics | Split into five single-purpose classes |
| Reads the file inside its constructor | Cannot be tested without a real file | `CSVLoader` is the only class that touches the file system; the others accept in-memory data |
| Validation rules written as repeated string literals | Rules drift apart between methods | Allowed values come from the model enums (one source of truth) |
| Prints results instead of returning them | Results cannot be asserted in tests or reused | Analytics methods return values; only `main.py` prints |
| Mutable list used as a class attribute for "processed tickets" | Shared across all instances; one run leaks data into the next | No mutable class attributes; `AnalyticsEngine` stores an instance-level tuple |

### 1.2 Key learnings

- **Instance vs class state.** Instance attributes belong to one object. Class attributes are shared by all instances, so they suit constants only. A mutable class attribute (for example, a list) is shared and changes leak between objects.
- **Dataclass constants.** A constant written as a dataclass field becomes per-instance data and part of `__init__`, `__eq__` and `__repr__`. `ClassVar` keeps it at class level and outside the generated methods.
- **Invariants.** `__post_init__` is where a dataclass validates its fields. With `frozen=True` the object cannot be changed after validation, so a ticket that exists stays valid.
- **`str` + `Enum`.** Because `Priority` subclasses `str`, a plain string such as `"zzz"` passes a loose type check. The model must check `isinstance(value, Priority)` explicitly.
- **Floating-point edge cases.** `float("inf")`, `float("nan")` and `float("1e400")` all parse successfully. `nan` makes every comparison false, so a range check such as `value < 0` does not catch it; `math.isfinite()` is required.
- **Composition over inheritance.** Use inheritance only for a genuine *is-a* relationship. None exists between loader, validator, cleaner and engine, so they are composed in `main.py`.

---

## 2. What I Can Explain Without Notes

- Why each of the five components has exactly one responsibility, and the dependency direction between them.
- The difference between class and instance state in this code, and why `MAX_DESCRIPTION_LENGTH` is a `ClassVar`.
- How `SupportTicket` prevents invalid state: type checks, enum membership, finiteness, ranges, and `frozen=True`.
- Why validation exists both in `TicketValidator` (explains problems in raw data) and in `SupportTicket` (guarantees typed objects are valid).
- Why `nan` passes ordinary comparisons and how `math.isfinite()` fixes it.
- How `csv.DictReader` handles rows with too many fields (key `None`) and too few fields (value `None`), and how the loader handles each.
- How the tests isolate file input with `tmp_path`, and why the single-class design would be harder to test.

---

## 3. Implementation Completed

| Task | Deliverable | Status |
|---|---|---|
| **A — Model the domain** | `SupportTicket` frozen dataclass; `Priority`, `Status`, `Category` enums; full field validation, including optional `resolution_time_hours` and `customer_rating` | Complete |
| **B — Separate responsibilities** | `CSVLoader`, `TicketValidator`, `DataCleaner`, `AnalyticsEngine` in separate modules; `main.py` composes them | Complete |
| **C — Extend behaviour** | `top_customers()`, `daily_volume()`, `average_resolution_time()`, `average_rating()` added without modifying existing methods | Complete |
| **D — Test and document** | 140 tests in six files; README with setup, assumptions, limitations and design rationale; this report; evidence logs | Complete |

### 3.1 Changes in this submission (after review of a peer's failed Day 02 assessment)

A peer's Day 02 code review failed for accepting invalid numeric values and crashing on malformed input. I checked my project against the same criteria, then probed it with additional adverse input. The defects found and fixed are listed in Section 5.

---

## 4. Tests / Experiment Results

```
$ python -m pytest -q -p no:cacheprovider
140 passed in 0.13s

$ python main.py
Loaded 10 raw rows from tickets.csv
Validation: 7 valid, 3 invalid
Constructed 7 SupportTicket objects
...  (exit code 0)

$ python main.py nope.csv
ERROR: File not found: ...\nope.csv   (exit code 1)
```

| Test file | Tests |
|---|---|
| `tests/test_ticket.py` | 41 |
| `tests/test_loader.py` | 13 |
| `tests/test_validator.py` | 46 |
| `tests/test_cleaner.py` | 14 |
| `tests/test_analytics.py` | 20 |
| `tests/test_pipeline.py` | 6 |
| **Total** | **140 passed, 0 failed** |

Full output is in `logs/test_results.txt` and `logs/pipeline_output.txt`. Environment: Windows 11, Python 3.12.10, pytest 9.2.0.

---

## 5. Bugs and Challenges with Root Causes

### 5.1 Main challenge — invalid ticket state was still possible

**Symptom:** `SupportTicket(priority="zzz", ...)`, `status=None` and `category=3` were all accepted, even though the model claimed that invalid tickets could not exist. Analytics would later fail when calling `.value` on these fields.

**Root cause:** type hints are not enforced at run time, and `__post_init__` only checked the text fields. Because `Priority` subclasses `str`, a plain string looks similar but is not a `Priority` member.

**Fix:** `__post_init__` now checks `isinstance(value, Priority/Category/Status)` and that text fields are real non-empty strings. Regression tests: `TestFieldTypesAreEnforced`. The relevant tests were rerun and pass.

### 5.2 All defects found and resolved

| # | Severity | Defect | Root cause | Fix and regression test |
|---|---|---|---|---|
| 1 | Critical | Surplus CSV field silently shifted every column | `csv.DictReader` stores extra values under key `None` without raising | Loader raises `ValueError` with row number — `test_loader.py` |
| 2 | Critical | `inf`, `nan`, `1e400` durations accepted; averages became `inf`/`nan` | `float()` parses them; `nan` fails every comparison, so range checks never trigger | `math.isfinite()` in model and validator — `TestOptionalNumericFields`, `TestNumericAndStructuralValidation` |
| 3 | Critical | Model accepted non-enum priority/status/category | Run-time type was never checked | `isinstance` checks — `TestFieldTypesAreEnforced` |
| 4 | High | Fractional rating (`3.5`, `4.0`) accepted | No integer check on rating | Integer and 1–5 range check — rating tests |
| 5 | High | Truncated CSV row crashed with `AttributeError` | `DictReader` fills missing cells with `None`; `None.strip()` fails | Loader pads with `""`; validator and cleaner are `None`-safe — `test_pipeline.py` |
| 6 | High | CSV saved from Excel: every row rejected as "missing id" | Excel writes a byte-order mark, so the first header became `﻿id` | Open with `utf-8-sig` — `test_excel_bom_is_removed` |
| 7 | Medium | Duplicate ticket IDs both accepted | Validation was row-level only | Batch check in `validate_all` — `TestDuplicateIds` |
| 8 | Medium | Non-UTF-8 file crashed with a raw `UnicodeDecodeError` traceback | Decoding error not translated | Clear `ValueError`; `main.py` exits with code 1 — `test_non_utf8_file_raises_clear_value_error` |
| 9 | Medium | Header ` ID ` or `ID` not recognised | Header names used as-is | Headers stripped and lower-cased — `test_header_names_are_stripped_and_lowercased` |
| 10 | Medium | Validator rejected `"URGENT"` | Case-sensitive comparison | `.lower()` before lookup — `test_uppercase_priority_is_accepted` |
| 11 | Medium | `DataCleaner` mutated the caller's rows | In-place dictionary assignment | Builds a new dictionary — `test_does_not_mutate_original` |
| 12 | Low | `MAX_DESCRIPTION_LENGTH` was per-instance; model was not frozen | Constant declared as a dataclass field | `ClassVar` and `frozen=True` — `test_constants_are_class_level_not_fields`, `test_ticket_is_frozen` |
| 13 | Low | `2_0` read as 20 hours | Python numeric parsing accepts underscores | Underscores rejected — validator parameterised tests |

---

## 6. Design Decision and Why

**Decision:** split processing into five composed components instead of one class or an inheritance hierarchy, and enforce rules both at the input boundary (`TicketValidator`) and at the model boundary (`SupportTicket`), using one shared source of rules.

**Why:**
- Each class has one reason to change, so changes stay local. Task C added four analytics methods without changing any existing code.
- Each class can be tested alone with in-memory data; only `CSVLoader` tests need temporary files.
- The validator explains problems in raw data to the person who owns the file; the model guarantees that any typed ticket is valid regardless of how it was created.
- Rules come from the enums and `ClassVar` constants, so the two validation layers cannot disagree.

The alternative designs are compared in README §9.1.

---

## 7. Blocker and What I Tried

**No open blocker.**

Resolved during the day: placing a constant inside a dataclass. Inside a `@dataclass`, any annotated attribute such as `MAX_DESCRIPTION_LENGTH: int = 500` becomes a field, so it appears in `__init__` and can be overridden per ticket. My first attempt, `field(default=500, init=False)`, removed it from `__init__`, but every instance still stored its own copy. The correct fix was `ClassVar[int]`, which tells the dataclass that the attribute is shared class state and not a field. This is verified by `test_constants_are_class_level_not_fields`.

Adding new fields after it also showed the ordering rule: fields with defaults (`resolution_time_hours = None`) must come after fields without defaults.

---

## 8. Acceptance Criteria Self-Check

| Criterion | Status | Evidence |
|---|---|---|
| Each component has one clear responsibility | Met | README §3–§4 |
| Class vs instance state is used correctly | Met | `ClassVar` constants; instance fields; no mutable class attributes |
| Invalid object state is prevented or explicitly represented | Met | `SupportTicket.__post_init__`; `None` for missing optional values; `Category.UNKNOWN` |
| Tests cover normal and invalid behaviour | Met | 140 tests; README §8 |
| Developer can explain why the design is maintainable | Prepared | README §9; Section 2 of this report (assessed in the viva) |

**Submission checklist:** source committed to Git with meaningful messages ✔ · actual test and pipeline output saved in `logs/` ✔ · README with setup, assumptions and limitations ✔ · logs included ✔ · implementation explainable without reading code line by line — to be demonstrated in the viva.

---

## 9. Tomorrow's Plan

- Push the Day 02 commits to the remote repository and confirm the code-review result.
- Prepare for the Day 02 technical viva by explaining each component and the defects in Section 5 without notes.
- Begin Day 03 when released, reusing the loader, validator and model as building blocks.
