# Day 01 closed-book answers

Write these answers from memory before reviewing the source code. These prompts are study guidance, not answers to copy.

## My answers

FILL IN: Explain how the processor handles missing values, invalid numeric values, duplicate IDs, and required-column errors.

FILL IN: Explain how the analytics calculate priority counts, average resolution time by category, average rating, and unresolved-ticket count.

FILL IN: Explain how the project keeps the raw CSV unchanged and how the tests verify that behavior.

## Runnable practice examples

Run these commands from the project root after installing the project in an active virtual environment:

```powershell
ticket-analytics analyze
ticket-analytics eda
python -m pytest -q
```

The first command analyzes `data/tickets.csv` and writes reports to `outputs/`. The second profiles the raw CSV. The last runs the automated test suite.
