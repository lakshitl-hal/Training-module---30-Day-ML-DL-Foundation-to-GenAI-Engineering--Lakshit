"""
api.py
======
FastAPI backend for the AI Support Intelligence Platform.

Endpoints
---------
GET  /              → health check
GET  /sample        → clean and analyze the bundled synthetic CSV
GET  /eda/sample    → profile the raw bundled synthetic CSV
POST /upload        → process an uploaded CSV, return EDA and analytics
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile

from ticket_analytics.analytics import (
    build_analytics_report,
    build_data_quality_summary,
)
from ticket_analytics.eda import build_eda_report
from ticket_analytics.processor import TicketDataProcessor, TicketProcessingError

# ── App setup ─────────────────────────────────────────────────
app = FastAPI(
    title="AI Support Intelligence Platform",
    description="Day 1 — Ticket Data Pipeline API",
    version="1.0.0",
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV = PROJECT_ROOT / "data" / "tickets_synthetic.csv"

# ── Helper ────────────────────────────────────────────────────

def _process_path(path: Path) -> dict[str, Any]:
    """Run the full pipeline and return a combined response dict."""
    processor = TicketDataProcessor(path)
    try:
        cleaned = processor.process()
    except TicketProcessingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    report = build_analytics_report(cleaned)
    raw = processor.raw
    if raw is None:
        raise RuntimeError("The processor completed without retaining its raw data.")
    eda = build_eda_report(raw)

    # Convert cleaned DataFrame rows to JSON-serialisable dicts
    tickets_json = (
        cleaned.astype(object)
        .where(pd.notna(cleaned), None)
        .to_dict(orient="records")
    )

    return {
        "analytics": report,
        "data_quality": build_data_quality_summary(processor.validation_report),
        "eda": eda,
        "validation": processor.validation_report,
        "quality_issues": processor.quality_issues.to_dict(orient="records"),
        "tickets": tickets_json,
    }


# ── Routes ────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def health():
    return {"status": "ok", "message": "AI Support Intelligence Platform API is running."}


@app.get("/sample", tags=["Pipeline"])
def run_sample():
    """Process the bundled synthetic dataset and return analytics + cleaned rows."""
    if not DEFAULT_CSV.exists():
        raise HTTPException(
            status_code=404, detail="Synthetic CSV dataset not found on server."
        )
    return _process_path(DEFAULT_CSV)


@app.get("/eda/sample", tags=["Pipeline"])
def run_sample_eda():
    """Return a raw-data exploratory profile for the bundled synthetic dataset."""
    if not DEFAULT_CSV.exists():
        raise HTTPException(status_code=404, detail="Synthetic CSV dataset not found.")
    raw = pd.read_csv(DEFAULT_CSV, dtype=str, keep_default_na=False)
    return build_eda_report(raw)


@app.post("/upload", tags=["Pipeline"])
async def upload_csv(file: UploadFile = File(...)):
    """
    Upload a CSV file, run the full pipeline, and return:
      - raw-data EDA report
      - analytics report
      - validation report (what was cleaned and why)
      - cleaned ticket rows
    """
    if not file.filename or Path(file.filename).suffix.lower() != ".csv":
        raise HTTPException(status_code=400, detail="Only .csv files are accepted.")

    contents = await file.read()

    # Write to a temp file so TicketDataProcessor can use Path-based loading
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp.write(contents)
        tmp_path = Path(tmp.name)

    try:
        result = _process_path(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    return result
