"""
src/main.py

FastAPI app entrypoint for Phase 1 (Review Enrichment).

Run locally:
    uvicorn src.main:app --reload

Note: this is the backend API app, distinct from the Streamlit
dashboard entrypoint (`app.py`) that Phase 4 will add at the project
root.
"""

from __future__ import annotations

from fastapi import FastAPI

from src.api.enrichment_router import router as enrichment_router
from src.api.analytics_router import router as analytics_router
from src.api.recommendation_router import router as recommendation_router
app = FastAPI(
    title="PointPulse AI API",
    description="Phase 1: Review Enrichment Pipeline",
    version="0.1.0",
)

app.include_router(enrichment_router)
app.include_router(analytics_router)
app.include_router(recommendation_router)

@app.get("/health", tags=["health"])
def health() -> dict:
    return {"status": "ok"}
