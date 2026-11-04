# Support Ticket Processing Pipeline

| Field | Value |
|---|---|
| **Programme** | 30-Day ML/DL Foundation to GenAI Engineering |
| **Module** | Day 02 — Object-Oriented Python & Reusable Modules |
| **Author** | Lakshit (HALCER) |
| **Date** | 03 November 2026 |
| **Status** | Submitted for code review (resubmission-ready) |
| **Test result** | 140 passed, 0 failed — see [`logs/test_results.txt`](logs/test_results.txt) |

---

## Contents

1. [Purpose](#1-purpose)
2. [Acceptance Criteria Mapping](#2-acceptance-criteria-mapping)
3. [Architecture](#3-architecture)
4. [Component Specifications](#4-component-specifications)
5. [Data Contract](#5-data-contract)
6. [Setup](#6-setup)
7. [Usage](#7-usage)
8. [Testing](#8-testing)
9. [Design Rationale](#9-design-rationale)
10. [Assumptions](#10-assumptions)
11. [Limitations](#11-limitations)
12. [Execution Evidence](#12-execution-evidence)

---

## 1. Purpose

This project refactors support-ticket processing into small, reusable, independently testable components. Raw CSV data is loaded, validated, cleaned, converted into typed domain objects and analysed. Each stage is a separate class with one responsibility, so a change to one concern (for example, the file format) does not require changes to the others.

The implementation uses the Python standard library only.

---

## 2. Acceptance Criteria Mapping

| # | Acceptance criterion (Day 02) | How it is met | Evidence |
|---|---|---|---|
| 1 | Each component has one clear responsibility | Five classes, one concern each: `CSVLoader` (read), `TicketValidator` (decide), `DataCleaner` (normalise), `SupportTicket` (represent), `AnalyticsEngine` (analyse). `main.py` only composes them. | §3, §4 |
| 2 | Class vs instance state is used correctly | Shared rules are class-level (`SupportTicket.MAX_DESCRIPTION_LENGTH`, `MIN_RATING`, `MAX_RATING` as `ClassVar`; `CSVLoader.SUPPORTED_EXTENSIONS` as an immutable `frozenset`). Per-object data is instance state (`ticket_id`, `_path`, `_tickets`). No mutable class attributes exist. | `test_constants_are_class_level_not_fields` |
| 3 | Invalid object state is prevented or explicitly represented | `SupportTicket` is a frozen dataclass validated in `__post_init__`: wrong types, empty text, non-enum values, `inf`/`nan`/negative durations and non-integer or out-of-range ratings raise `ValueError`. Missing optional values are represented explicitly as `None`; unrecognised categories as `Category.UNKNOWN`. Invalid CSV rows are reported in `ValidationResult`, never silently dropped. | `tests/test_ticket.py`, `tests/test_validator.py` |
| 4 | Tests cover normal and invalid behaviour | 140 tests across six files, including end-to-end malformed-input tests through loader → validator → cleaner → model. | §8, `logs/test_results.txt` |
| 5 | Developer can explain why the design is maintainable | Two designs compared and justified in §9. | §9 |

**Task coverage:** Task A — `src/models/ticket.py`; Task B — `src/io`, `src/validation`, `src/processing`, `src/analytics`; Task C — `top_customers()`, `daily_volume()`, `average_resolution_time()`, `average_rating()` added without changing existing methods; Task D — `tests/`, this README, `DAILY_REPORT.md`.

---

## 3. Architecture

### 3.1 Pipeline flow

```
data/tickets.csv
      │
      ▼
CSVLoader ─────────── reads rows as dict[str, str]; rejects surplus fields;
      │               pads truncated rows with ""; removes Excel BOM
      ▼
TicketValidator ───── per-row business rules + duplicate-ID check;
      │               returns one ValidationResult per row
      ▼  (valid rows only)
DataCleaner ───────── strips whitespace, normalises case, maps to enum values;
      │               never mutates its input
      ▼
SupportTicket ─────── frozen, typed domain object; invariants enforced
      │               in __post_init__
      ▼
AnalyticsEngine ───── pure read-only analytics over an immutable tuple
```

### 3.2 Dependency direction

`models` is the innermost layer and imports nothing from the project. `validation`, `processing` and `analytics` import from `models` only. `io` imports nothing from the project. `main.py` is the only module that knows about all of them. This prevents circular imports and keeps each layer testable on its own.

### 3.3 Repository structure

```
DAY_2_OOPS/
├── data/tickets.csv              Sample dataset — 10 rows, 3 intentionally invalid
├── src/
│   ├── models/ticket.py          SupportTicket, Priority, Status, Category
│   ├── io/loader.py              CSVLoader
│   ├── validation/validator.py   TicketValidator, ValidationResult
│   ├── processing/cleaner.py     DataCleaner
│   └── analytics/engine.py       AnalyticsEngine
├── tests/
│   ├── test_ticket.py            41 tests — model invariants, types, immutability
│   ├── test_loader.py            13 tests — file, encoding, header, field-count integrity
│   ├── test_validator.py         46 tests — row rules, numeric rules, duplicates
│   ├── test_cleaner.py           14 tests — normalisation, no input mutation
│   ├── test_analytics.py         20 tests — counts, filters, averages, empty input
│   └── test_pipeline.py           6 tests — end-to-end and CLI behaviour
├── logs/
│   ├── test_results.txt          Actual pytest -v output
│   └── pipeline_output.txt       Actual python main.py output
├── main.py                       Composition root / command-line entry point
├── README.md                     This document
└── DAILY_REPORT.md               Day 02 daily report
```

---

## 4. Component Specifications

### 4.1 `SupportTicket` — domain model (`src/models/ticket.py`)

**Responsibility:** represent one valid support ticket. A `SupportTicket` that exists is always valid.

| Field | Type | Rule (violations raise `ValueError`) |
|---|---|---|
| `ticket_id` | `str` | Non-empty, non-whitespace string |
| `customer` | `str` | Non-empty, non-whitespace string |
| `priority` | `Priority` | Must be a `Priority` member (a plain `"high"` string is rejected) |
| `category` | `Category` | Must be a `Category` member |
| `status` | `Status` | Must be a `Status` member |
| `description` | `str` | Non-empty; at most `MAX_DESCRIPTION_LENGTH` (500) characters |
| `created_at` | `datetime` | Must be a `datetime` instance |
| `resolution_time_hours` | `float \| None` | `None`, or a finite number ≥ 0 (`inf`, `-inf`, `nan`, `bool` rejected) |
| `customer_rating` | `int \| None` | `None`, or an integer from 1 to 5 (`3.5`, `4.0`, `True` rejected) |

Class-level constants (`ClassVar`): `MAX_DESCRIPTION_LENGTH = 500`, `MIN_RATING = 1`, `MAX_RATING = 5`.
Derived properties: `is_open` (status is OPEN or PENDING), `is_high_priority` (HIGH or URGENT).
The class is `@dataclass(frozen=True)`: fields cannot be reassigned after construction.

### 4.2 `CSVLoader` — file input (`src/io/loader.py`)

**Responsibility:** read a CSV file into a list of string dictionaries. It does not interpret values.

| Condition | Behaviour |
|---|---|
| File does not exist | `FileNotFoundError` |
| Extension is not `.csv` | `ValueError` |
| File is not valid UTF-8 | `ValueError` with a clear message (no raw `UnicodeDecodeError`) |
| File starts with a UTF-8 byte-order mark (Excel) | BOM removed; first column read correctly |
| Header names with spaces or capitals (` ID `) | Normalised to lower case, stripped (`id`) |
| Row has **more** fields than the header | `ValueError` naming the row and surplus values (prevents silent column shift) |
| Row has **fewer** fields than the header | Missing cells become `""`; the validator then reports them |

### 4.3 `TicketValidator` — validation (`src/validation/validator.py`)

**Responsibility:** decide whether each raw row is usable and explain why not. It does not modify rows.

1. `id`, `customer`, `priority`, `category`, `status`, `description`, `created_at` are present and non-empty.
2. `priority` and `status` (case-insensitive) are valid enum values. The allowed sets are derived from the model enums — one source of truth.
3. `created_at` is a valid ISO 8601 date or date-time.
4. `description` is at most 500 characters.
5. `resolution_time_hours`, if present, is a plain number, finite and ≥ 0.
6. `customer_rating`, if present, is a whole number from 1 to 5.
7. `id` is unique in the batch; the first occurrence is kept and later duplicates are rejected.

Each row produces a `ValidationResult(row_index, is_valid, errors)`, so every rejection is visible in the output.

### 4.4 `DataCleaner` — normalisation (`src/processing/cleaner.py`)

**Responsibility:** turn validated rows into canonical values ready for the model. It always returns new dictionaries and never mutates its input.

| Field | Transformation |
|---|---|
| All fields | Whitespace stripped (`None`-safe) |
| `priority`, `status` | Lower-cased and mapped to enum values |
| `category` | Lower-cased; unrecognised values map to `unknown` (explicit representation) |
| `customer` | Title-cased |

### 4.5 `AnalyticsEngine` — analytics (`src/analytics/engine.py`)

**Responsibility:** compute read-only statistics. The engine stores tickets as a tuple, so callers cannot change its data after construction.

| Method | Returns |
|---|---|
| `total_count()` | `int` |
| `count_by_priority()` / `count_by_status()` / `count_by_category()` | `dict[str, int]` |
| `open_tickets()` / `high_priority_open()` | `list[SupportTicket]` |
| `top_customers(n=3)` *(Task C)* | `list[tuple[str, int]]` |
| `daily_volume()` *(Task C)* | `dict[str, int]` sorted by date |
| `average_resolution_time()` *(Task C)* | `float`, or `None` if no ticket has a value |
| `average_rating()` *(Task C)* | `float`, or `None` if no ticket is rated |
| `summary_report()` | Formatted text report |

---

## 5. Data Contract

### 5.1 Input columns

| Column | Required | Type | Valid values |
|---|---|---|---|
| `id` | Yes | text | Non-empty, unique in the file |
| `customer` | Yes | text | Non-empty |
| `priority` | Yes | text | `low`, `medium`, `high`, `urgent` (any case) |
| `category` | Yes | text | `billing`, `technical`, `account`, `general`; anything else becomes `unknown` |
| `status` | Yes | text | `open`, `pending`, `resolved`, `closed` (any case) |
| `description` | Yes | text | Non-empty, at most 500 characters |
| `resolution_time_hours` | No | number | Empty, or finite and ≥ 0 |
| `customer_rating` | No | integer | Empty, or 1–5 |
| `created_at` | Yes | date | ISO 8601, e.g. `2024-01-15` or `2024-01-15T10:30:00` |

### 5.2 Sample data

```csv
id,customer,priority,category,status,description,resolution_time_hours,customer_rating,created_at
T001,Alice Johnson,high,billing,open,Cannot access invoice for last month,,, 2024-01-15
T002,Bob Smith,low,technical,closed,App crashes on startup,4.5,4,2024-01-16
T003,,medium,billing,open,Duplicate charge on account,2,5,2024-01-17
```

Rows 3, 6 and 8 of `data/tickets.csv` are intentionally invalid (missing customer, description or category) to demonstrate rejection and reporting.

---

## 6. Setup

**Prerequisites:** Python 3.10 or later (developed and tested on Python 3.12.10); `pytest` for the tests (tested with pytest 9.2.0). No other packages are needed.

```bash
git clone <repository-url>
cd DAY_2_OOPS
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install pytest
```

---

## 7. Usage

Run all commands from the project root.

```bash
python main.py                         # process data/tickets.csv
python main.py path/to/other.csv       # process another file
```

**Exit codes:** `0` when the run succeeds; `1` when the file cannot be used (missing, wrong extension, not UTF-8, or a row with surplus fields). File-level errors are printed to standard error as `ERROR: ...`. Row-level problems do not stop the run; they are listed in the output.

Excerpt of actual output (full output in `logs/pipeline_output.txt`):

```
Loaded 10 raw rows from tickets.csv

Validation: 7 valid, 3 invalid
  Row 3: INVALID — missing or empty 'customer'
  Row 6: INVALID — missing or empty 'description'
  Row 8: INVALID — missing or empty 'customer'; missing or empty 'category'

Constructed 7 SupportTicket objects
...
Average resolution time: 3.80 h
Average customer rating: 3.83 / 5
```

---

## 8. Testing

```bash
python -m pytest -v
```

| File | Tests | Normal behaviour | Invalid / edge behaviour |
|---|---|---|---|
| `test_ticket.py` | 41 | Valid construction, properties, `__str__` | Empty and whitespace text; non-string text; non-enum priority/status/category; `inf`, `-inf`, `nan`, negative, non-numeric durations; `3.5`, `4.0`, `True`, `0`, `6` ratings; frozen fields; 501-character description |
| `test_loader.py` | 13 | Rows returned as dictionaries | Missing file; wrong extension; surplus fields; Excel BOM; messy headers; non-UTF-8 file; header-only file |
| `test_validator.py` | 46 | Valid rows; any-case priority | Missing fields; unknown values; invalid dates; `inf`/`nan`/`1e400`/`2_0` durations; fractional ratings; `None` values; missing keys; duplicate IDs |
| `test_cleaner.py` | 14 | Stripping, normalisation, title case | Unknown values; `None` values; input not mutated |
| `test_analytics.py` | 20 | Counts, filters, top customers, daily volume, averages | Empty collection; tickets without optional values |
| `test_pipeline.py` | 6 | Sample file end-to-end; Excel-saved file | Truncated rows; non-finite and fractional values; unusable file → exit code 1 |
| **Total** | **140** | | **140 passed, 0 failed** |

Tests that need a file create a temporary one with pytest's `tmp_path` fixture, so they do not depend on the real data file or on each other.

---

## 9. Design Rationale

### 9.1 Two designs compared

| Concern | Design 1: one `TicketProcessor` class | Design 2 (chosen): composed components |
|---|---|---|
| Responsibilities | Loads, validates, cleans and analyses in one class | One class per concern |
| Reasons to change | Four (file format, rules, cleaning, metrics) | One per class |
| Testing | Every test needs a real file and runs the whole flow | Each class is tested alone with in-memory data |
| Adding an analysis | Edit the large class; risk breaking other steps | Add a method to `AnalyticsEngine` only |
| Changing the source (e.g. JSON) | Rewrite part of the class | Add a new loader; other classes unchanged |

**Decision:** Design 2. It has low coupling (components communicate through plain dictionaries and `SupportTicket` objects), high cohesion (each class's methods serve one concern), and it is easy to test. That is why Task C could add four analytics methods without changing any existing behaviour.

### 9.2 Composition over inheritance

No component *is a* kind of another: an analytics engine is not a ticket, and a validator is not a loader. Inheritance would add coupling without benefit, so `main.py` composes independent objects instead. The only inheritance used is `class Priority(str, Enum)`, where the members genuinely are strings.

### 9.3 Invariants at the model boundary, rules at the input boundary

Validation exists in two places on purpose. `TicketValidator` checks raw text and explains every problem so the data owner can fix the file. `SupportTicket` checks typed values so no other code path can create an invalid ticket, even code that does not use the validator. Both read their rules from the same source (the enums and the `ClassVar` constants), so they cannot drift apart.

### 9.4 Explicit failure instead of silent corruption

A row with too many fields would shift every column (`id` would receive the category). The loader stops with a clear error instead of returning wrong data. Row-level problems are reported per row, so nothing is dropped without a reason.

---

## 10. Assumptions

| # | Assumption |
|---|---|
| 1 | Input files are UTF-8 (with or without a byte-order mark). |
| 2 | The header row contains the column names in §5.1; names are matched case-insensitively. |
| 3 | `created_at` uses ISO 8601 format. |
| 4 | Ticket IDs should be unique within one file; the first occurrence is treated as authoritative. |
| 5 | An empty optional cell means "not recorded", represented as `None`. |
| 6 | The whole file fits in memory. |

---

## 11. Limitations

| # | Limitation | Impact |
|---|---|---|
| 1 | Only CSV input is supported | Other formats need a new loader class |
| 2 | Output is printed text only | No file export or charts |
| 3 | Duplicate detection is within one file only | Duplicates across separate runs are not detected |
| 4 | No check between status and resolution time | An open ticket with a resolution time is accepted |
| 5 | A truncated row that loses only optional columns is accepted | Those values become `None` (unknown) |
| 6 | Unrecognised categories are mapped to `unknown`, not rejected | Deliberate explicit representation; visible in the category counts |
| 7 | Files are processed sequentially in memory | Not designed for very large datasets |

---

## 12. Execution Evidence

| File | Content | Command |
|---|---|---|
| [`logs/test_results.txt`](logs/test_results.txt) | Full test output — 140 passed, 0 failed | `python -m pytest -v -p no:cacheprovider` |
| [`logs/pipeline_output.txt`](logs/pipeline_output.txt) | Full pipeline output on the sample data | `python main.py` |

Environment: Windows 11, Python 3.12.10, pytest 9.2.0.
