# Day 01 Daily Report — Ticket Data Pipeline

- **Developer:** Lakshit Likhar
- **Assignment:** Day 01 — Python Engineering & Ticket Data Pipeline
- **Date:** 2026-11-02
- **Repository URL:** https://github.com/lakshitl-hal/DAY-1-HALCER-TRAINING-ASSIGNMENT
- **Branch:** `main`
- **Latest commit hash:** `da240d3`
- **Pull Request:** N/A — the refactor branch was fast-forwarded into `main`; no pull request was created.

## Objective

Build a reliable support-ticket CSV pipeline that validates and cleans data, calculates required metrics, reports data-quality findings, and verifies behavior with automated tests.

## Work completed

- Kept the required `tickets.csv` dataset and the larger synthetic CRM dataset.
- Refactored the processor into focused cleaning methods and consolidated bounded numeric validation.
- Improved CSV loading errors and shared the active ticket-status definition.
- Separated analytics calculations from console and CSV report output.
- Added raw missing-value, invalid-value, duplicate-ID, and missing-ID summaries to CLI and API results.
- Made the required dataset the default for CLI analysis and EDA.
- Added regression tests for malformed CSV, non-finite numeric values, blank values, non-unique indexes, and unknown statuses.
- Documented cleaning rules, assumptions, limitations, and manually checked fixture metrics.

## Verification

- **Test command:** `python -m pytest -v`
- **Test result:** 40 tests passed.
- **Test evidence:** [docs/test_output.txt](./docs/test_output.txt)
- **Manual metric checks:** The required fixture reports 8 unresolved tickets, an average rating of 3.67, and a Technical average resolution time of 6.5 hours. Additional category calculations and arithmetic are documented in [README.md](./README.md).
- **Git status:** `main` is at `da240d3`, matching `origin/main`; this review refreshed the test log and leaves documentation edits uncommitted.

## What I learned

FILL IN: (write what I learned in my own words).

## Resubmission status

- The refactor and follow-up documentation/test commits are on `main`.
- The raw `data/tickets.csv` rows were not modified.
- The complete verbose test output is saved in `docs/test_output.txt`.
- No `outputs/`, virtual-environment, or Python cache directories are tracked.

## Final checks before submission

- Review [README.md](./README.md) for setup, cleaning rules, assumptions, limitations, and manual calculations.
- Review [docs/test_output.txt](./docs/test_output.txt) for the actual verbose test result.
- Fill in the personal learning notes in this report and the answers in [docs/day01_study_answers.md](./docs/day01_study_answers.md).
- Confirm the GitHub repository still contains the latest `main` branch.
