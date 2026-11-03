# Support Ticket Processing Pipeline

**Programme:** 30-Day ML/DL Foundation to GenAI Engineering
**Module:** Day 02 — Object-Oriented Python & Reusable Modules
**Version:** 1.0.0
**Status:** Complete
**Author:** Lakshit (HALCER)
**Date:** 03 November 2026

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Module Specifications](#3-module-specifications)
4. [Data Contract](#4-data-contract)
5. [Installation & Setup](#5-installation--setup)
6. [Usage](#6-usage)
7. [Test Suite](#7-test-suite)
8. [Design Rationale](#8-design-rationale)
9. [OOP Concepts Reference](#9-oop-concepts-reference)

---

## 1. Overview

### 1.1 Purpose

This module implements a fully object-oriented **Support Ticket Processing Pipeline** in Python. It demonstrates core software engineering principles — Single Responsibility, encapsulation, composition, and defensive validation — applied to a realistic data-processing domain.

### 1.2 Scope

The pipeline accepts raw CSV data containing support ticket records, processes it through a series of isolated, testable components, and produces structured analytics output. Each stage of processing is implemented as an independent class with a clearly defined interface and a single reason to change.

### 1.3 Learning Objectives

| Objective | Requirement |
|---|---|
| Component responsibility | Each class has exactly one clearly defined concern |
| State management | Class-level and instance-level state are used appropriately and never conflated |
| Defensive construction | An object in an invalid state cannot be constructed |
| Test coverage | Every module is covered by tests for both valid and invalid inputs |

---

## 2. Architecture

### 2.1 Pipeline Flow

```
CSV File on Disk
      │
      ▼
┌─────────────┐
│  CSVLoader  │  Reads raw rows as plain dictionaries.
│  (src/io)   │  Rejects any row where field count exceeds header count.
└──────┬──────┘
       │  list[dict[str, str]]
       ▼
┌──────────────────┐
│ TicketValidator  │  Applies business rules to each row.
│ (src/validation) │  Returns ValidationResult per row; separates valid from invalid.
└────────┬─────────┘
         │  list[dict[str, str]]  (valid rows only)
         ▼
┌──────────────┐
│ DataCleaner  │  Normalises casing, maps values to canonical Enum strings.
│ (src/process)│  Never mutates the input; always returns a new list.
└──────┬───────┘
       │  list[dict[str, str]]  (cleaned rows)
       ▼
┌────────────────┐
│ SupportTicket  │  Typed domain object. Built from cleaned rows.
│ (src/models)   │  __post_init__ enforces invariants at construction time.
└──────┬─────────┘
       │  Sequence[SupportTicket]
       ▼
┌──────────────────┐
│ AnalyticsEngine  │  Computes metrics over the ticket collection.
│ (src/analytics)  │  Pure methods — no side effects, no mutation.
└──────────────────┘
```

### 2.2 Repository Structure

```
DAY_2_OOPS/
│
├── data/
│   └── tickets.csv                  Sample dataset — 10 rows, 3 intentionally invalid
│
├── src/
│   ├── __init__.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── ticket.py                Domain model: SupportTicket, Priority, Status, Category
│   ├── io/
│   │   ├── __init__.py
│   │   └── loader.py                CSVLoader — file reading and field-count integrity
│   ├── validation/
│   │   ├── __init__.py
│   │   └── validator.py             TicketValidator — business rule enforcement
│   ├── processing/
│   │   ├── __init__.py
│   │   └── cleaner.py               DataCleaner — normalisation and canonicalisation
│   └── analytics/
│       ├── __init__.py
│       └── engine.py                AnalyticsEngine — metrics and reporting
│
├── tests/
│   ├── __init__.py
│   ├── test_ticket.py               12 tests — model construction and properties
│   ├── test_loader.py               9 tests  — file loading and field-count integrity
│   ├── test_validator.py            16 tests — validation rules and edge cases
│   ├── test_cleaner.py              13 tests — normalisation and immutability
│   └── test_analytics.py           17 tests — metrics, filters, and edge cases
│
├── main.py                          End-to-end pipeline demonstration
├── README.md                        This document
└── DAILY_REPORT.md                  Daily learning and implementation report
```

---

## 3. Module Specifications

### 3.1 `SupportTicket` — Domain Model (`src/models/ticket.py`)

**Responsibility:** Define the canonical representation of a single support ticket. Enforce all field invariants at construction time so that no invalid ticket object can exist.

| Attribute | Type | Constraint |
|---|---|---|
| `ticket_id` | `str` | Must be non-empty and non-whitespace |
| `customer` | `str` | Must be non-empty and non-whitespace |
| `priority` | `Priority` | Enum: `low`, `medium`, `high`, `urgent` |
| `category` | `Category` | Enum: `billing`, `technical`, `account`, `general`, `unknown` |
| `status` | `Status` | Enum: `open`, `pending`, `resolved`, `closed` |
| `description` | `str` | Must be non-empty; max 500 characters |
| `created_at` | `datetime` | Standard Python datetime |

**Derived properties:**

| Property | Returns | Logic |
|---|---|---|
| `is_open` | `bool` | `True` when status is `OPEN` or `PENDING` |
| `is_high_priority` | `bool` | `True` when priority is `HIGH` or `URGENT` |

---

### 3.2 `CSVLoader` — File I/O (`src/io/loader.py`)

**Responsibility:** Read rows from a CSV file on disk and return them as plain string-valued dictionaries. Enforce file existence, file type, and field-count integrity. Perform no interpretation or validation of field values.

**Class attribute:** `SUPPORTED_EXTENSIONS: frozenset[str]` — currently `{".csv"}`

**Error conditions:**

| Condition | Exception Raised |
|---|---|
| File does not exist | `FileNotFoundError` |
| File extension not in supported set | `ValueError` |
| Any data row contains more fields than the header | `ValueError` with row number and surplus values |

> **Design note:** When `csv.DictReader` receives a row with surplus fields, it stores the extra values under the dictionary key `None`. This silently shifts all column values, causing ticket IDs to become category names and corrupting the entire row. The loader detects this condition and raises immediately, ensuring corrupted data never reaches downstream components.

---

### 3.3 `TicketValidator` — Validation (`src/validation/validator.py`)

**Responsibility:** Apply business rules to raw string-valued rows and report the outcome. The validator does not clean, transform, or persist data.

**Validation rules applied per row:**

1. All seven required fields (`id`, `customer`, `priority`, `category`, `status`, `description`, `created_at`) must be present and non-empty after stripping whitespace.
2. `priority` value, after lowercasing, must be one of `{low, medium, high, urgent}`.
3. `status` value, after lowercasing, must be one of `{open, pending, resolved, closed}`.

**Return type:** `ValidationResult` dataclass carrying `row_index`, `is_valid`, and `errors: list[str]`.

---

### 3.4 `DataCleaner` — Normalisation (`src/processing/cleaner.py`)

**Responsibility:** Transform validated raw rows into normalised, canonicalised dictionaries ready for domain-object construction. The input sequence is never mutated.

**Normalisation rules applied per row:**

| Field | Transformation |
|---|---|
| All fields | Leading and trailing whitespace stripped |
| `priority` | Lowercased; mapped to canonical Enum value; unknown values default to `low` |
| `status` | Lowercased; mapped to canonical Enum value; unknown values default to `open` |
| `category` | Lowercased; mapped to canonical Enum value; unknown values default to `unknown` |
| `customer` | Title-cased (e.g. `alice johnson` → `Alice Johnson`) |

---

### 3.5 `AnalyticsEngine` — Analytics (`src/analytics/engine.py`)

**Responsibility:** Compute metrics and generate reports over an immutable collection of `SupportTicket` objects. All methods are pure — they read data and return new structures without mutation.

**Available operations:**

| Method | Returns | Description |
|---|---|---|
| `total_count()` | `int` | Total number of tickets in the collection |
| `count_by_priority()` | `dict[str, int]` | Frequency map per priority level |
| `count_by_status()` | `dict[str, int]` | Frequency map per status |
| `count_by_category()` | `dict[str, int]` | Frequency map per category |
| `open_tickets()` | `list[SupportTicket]` | Tickets with status OPEN or PENDING |
| `high_priority_open()` | `list[SupportTicket]` | Open tickets with priority HIGH or URGENT |
| `top_customers(n)` | `list[tuple[str, int]]` | Top n customers by ticket volume |
| `daily_volume()` | `dict[str, int]` | Ticket count grouped by calendar date |
| `summary_report()` | `str` | Formatted human-readable summary |

---

## 4. Data Contract

### 4.1 Input CSV Format

The CSV file must conform to the following schema. All fields are required.

| Column | Type | Valid Values |
|---|---|---|
| `id` | string | Non-empty unique identifier (e.g. `T001`) |
| `customer` | string | Non-empty customer name |
| `priority` | string | `low`, `medium`, `high`, `urgent` (case-insensitive) |
| `category` | string | `billing`, `technical`, `account`, `general` (case-insensitive) |
| `status` | string | `open`, `pending`, `resolved`, `closed` (case-insensitive) |
| `description` | string | Non-empty; max 500 characters |
| `created_at` | ISO 8601 date | e.g. `2024-01-15` |

### 4.2 Sample Data

```csv
id,customer,priority,category,status,description,created_at
T001,Alice Johnson,high,billing,open,Cannot access invoice for last month,2024-01-15
T002,Bob Smith,low,technical,closed,App crashes on startup,2024-01-16
T003,,medium,billing,open,Duplicate charge on account,2024-01-17
```

Rows 3, 6, and 8 of the sample dataset are intentionally invalid to demonstrate validation and rejection behaviour.

---

## 5. Installation & Setup

### 5.1 Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.10 or higher |
| pytest | Any recent version |

### 5.2 Environment Setup

No third-party packages are required. All modules use the Python standard library only (`csv`, `dataclasses`, `enum`, `pathlib`, `collections`, `datetime`).

```bash
# Verify Python version
python --version

# Verify pytest is available
python -m pytest --version
```

---

## 6. Usage

### 6.1 Run the Full Pipeline

```bash
python main.py
```

This executes all five pipeline stages against the sample dataset and prints a formatted analytics report to stdout.

### 6.2 Expected Output

```
Loaded 10 raw rows from tickets.csv

Validation: 7 valid, 3 invalid
  Row 3: INVALID — missing or empty 'customer'
  Row 6: INVALID — missing or empty 'description'
  Row 8: INVALID — missing or empty 'category'; missing or empty 'customer'

Constructed 7 SupportTicket objects

==================================================
       SUPPORT TICKET ANALYTICS REPORT
==================================================
  Total tickets      : 7
  Open / Pending     : 4
  High-priority open : 3

  By Priority:
    high       : 2
    low        : 2
    medium     : 2
    urgent     : 1

  By Status:
    closed     : 2
    open       : 2
    pending    : 2
    resolved   : 1

  By Category:
    account    : 1
    billing    : 2
    technical  : 3
    unknown    : 1
==================================================

High-priority open tickets needing attention:
  [T001] Alice Johnson | HIGH | open | Cannot access invoice for last month...
  [T004] Carol White | URGENT | pending | Cannot login to account...
  [T009] Grace Lee | HIGH | open | Data not syncing across devices...

Daily ticket volume:
  2024-01-15: # (1)
  2024-01-16: # (1)
  ...
```

### 6.3 Using Individual Modules

Each module can be imported and used independently:

```python
from src.io.loader import CSVLoader
from src.validation.validator import TicketValidator
from src.processing.cleaner import DataCleaner
from src.analytics.engine import AnalyticsEngine

# Load
rows = CSVLoader("data/tickets.csv").load()

# Validate
validator = TicketValidator()
valid_rows = validator.filter_valid(rows)

# Clean
cleaned = DataCleaner().clean_all(valid_rows)
```

---

## 7. Test Suite

### 7.1 Running Tests

```bash
# Run the full suite with verbose output
python -m pytest tests/ -v

# Run a specific module's tests
python -m pytest tests/test_ticket.py -v
python -m pytest tests/test_loader.py -v
python -m pytest tests/test_validator.py -v
python -m pytest tests/test_cleaner.py -v
python -m pytest tests/test_analytics.py -v
```

### 7.2 Test Coverage Summary

| Test File | Tests | Scenarios Covered |
|---|---|---|
| `test_ticket.py` | 12 | Valid construction, empty-field rejection, whitespace-only rejection, property logic |
| `test_loader.py` | 9 | File not found, wrong extension, extra-field integrity, correct field count, empty CSV |
| `test_validator.py` | 16 | All required fields, unknown priority/status, whitespace fields, multiple errors, filter logic |
| `test_cleaner.py` | 13 | Whitespace stripping, priority/status/category normalisation, title-casing, immutability, empty input |
| `test_analytics.py` | 17 | Count methods, open/closed filtering, high-priority logic, top customers, daily volume, empty collection |
| **Total** | **67** | **67 passed, 0 failed** |

### 7.3 Key Regression Test

The loader test suite includes a regression test for the exact malformed-CSV scenario where a surplus field causes `csv.DictReader` to shift column values silently:

```
id,category,priority,description,resolution_time_hours,customer_rating,status
T-101,Billing,High,Valid,2,5,Closed,UNEXPECTED
```

**Expected behaviour:** `ValueError` raised immediately with row number and surplus values.
**Prohibited behaviour:** Returning rows where `id == "Billing"`.

---

## 8. Design Rationale

### 8.1 Single Responsibility Over God Object

A monolithic `TicketProcessor` class that performs loading, validation, cleaning, and analytics simultaneously would violate the Single Responsibility Principle. Any change to one concern — for example, switching from CSV to JSON input — would require modifying and retesting the entire class.

The pipeline is instead decomposed into five classes. Each class has exactly one reason to change, can be tested in complete isolation, and can be replaced independently.

### 8.2 Composition Over Inheritance

`AnalyticsEngine` accepts tickets as a constructor argument (composition). It does not inherit from a base class. There is no genuine "is-a" relationship between an analytics engine and a ticket — composition is therefore the correct model. This also makes it straightforward to add new analytics methods without modifying or subclassing existing code.

### 8.3 Invariant Enforcement at Construction

`SupportTicket.__post_init__` validates all fields immediately upon construction. An invalid ticket object cannot be created. Downstream code — `DataCleaner`, `AnalyticsEngine`, `main.py` — can therefore operate without defensive null-checks or guard clauses on ticket fields.

### 8.4 Immutability of Input Data

`DataCleaner._clean_row` always begins by creating a copy of the input dictionary (`dict(row)`). The original rows passed by the caller are never modified. This eliminates a class of bugs where later pipeline stages receive unexpectedly mutated data.

---

## 9. OOP Concepts Reference

| Concept | Implementation Location | Notes |
|---|---|---|
| `@dataclass` with `__post_init__` | `src/models/ticket.py` | Auto-generates `__init__`, `__repr__`, `__eq__`; `__post_init__` enforces invariants |
| `Enum` with `str` mixin | `src/models/ticket.py` | `Priority(str, Enum)` allows direct string comparison and JSON serialisation |
| Class attribute vs instance attribute | `src/io/loader.py` | `SUPPORTED_EXTENSIONS` is class-level (shared); `self._path` is instance-level (per-object) |
| Encapsulation via naming convention | All `src/` modules | Methods prefixed with `_` are implementation details, not public API |
| `@property` for derived state | `src/models/ticket.py` | `is_open`, `is_high_priority` computed from existing fields; no redundant stored state |
| `__repr__` and `__str__` | All classes | `__repr__` for unambiguous developer output; `__str__` for human-readable display |
| Composition | `src/analytics/engine.py` | Engine receives tickets; does not inherit from any ticket-related base |
| Type annotations | All modules | Full PEP 484 annotations; `from __future__ import annotations` for forward references |

---

## 10. Assumptions

| # | Assumption | Rationale |
|---|---|---|
| 1 | The input CSV file is UTF-8 encoded | Standard encoding for data interchange; the loader opens files with `encoding="utf-8"` |
| 2 | The CSV header row contains exactly the seven required columns | The pipeline validates field presence per row; header column names must match the expected schema |
| 3 | `created_at` values conform to ISO 8601 date format (YYYY-MM-DD) | `datetime.fromisoformat()` is used for parsing; non-ISO formats will raise `ValueError` |
| 4 | Ticket IDs are unique within the dataset | The pipeline does not perform deduplication; duplicate IDs will be processed as separate tickets |
| 5 | The dataset fits in memory | All rows are loaded into a list; no streaming or chunked processing is implemented |
| 6 | No third-party packages are required | The entire project uses the Python standard library only |

---

## 11. Limitations

| # | Limitation | Impact |
|---|---|---|
| 1 | No persistent storage or database integration | Output is printed to stdout; the pipeline does not write cleaned data to disk |
| 2 | No duplicate ticket detection | If the same ticket ID appears twice, both records are processed independently |
| 3 | Validation is row-level only | Cross-row constraints (e.g., unique IDs, referential integrity) are not enforced |
| 4 | Single file format supported | Only `.csv` files are accepted; JSON, Excel, or API sources require a new loader class |
| 5 | No concurrency or parallel processing | The pipeline runs sequentially; performance is not optimised for large datasets |
| 6 | Analytics output is text only | No graphical visualisation, no export to HTML/PDF; output is formatted for terminal display |
| 7 | Description length cap is fixed at 500 characters | The `MAX_DESCRIPTION_LENGTH` constant is set at class level and is not configurable at runtime |

---

## 12. Execution Evidence

Test results and pipeline output logs are captured in the `logs/` directory for submission verification:

| Log File | Content |
|---|---|
| `logs/test_results.txt` | Full `pytest -v` output — 67 passed, 0 failed |
| `logs/pipeline_output.txt` | Full `main.py` execution output — load, validate, clean, analyse |

---

*End of Document*
