"""
src/api/enrichment_router.py

Phase 1 API surface: POST /api/enrich.

Thin by design — all pipeline logic lives in EnrichmentService, all
Gemini logic lives in GeminiClient. This module's only job is HTTP
plumbing: constructing the service, calling it, and translating
exceptions into appropriate status codes.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.ai.gemini_client import GeminiClient, GeminiClientError
from src.services.enrichment_service import EnrichmentFailure, EnrichmentService

router = APIRouter(prefix="/api", tags=["enrichment"])


class EnrichResponse(BaseModel):
    processed: int
    failed: list[EnrichmentFailure] = Field(default_factory=list)
    skipped: int


@router.post("/enrich", response_model=EnrichResponse)
def enrich_reviews() -> EnrichResponse:
    """
    Run one full enrichment pass over `data/reviews.csv`.

    - Rows already marked `processed == True` are skipped.
    - Successfully enriched rows are written/upserted into
      `data/enriched_reviews.csv` and flipped to `processed == True`.
    - Rows that fail (Gemini error or schema-validation error) are left
      `processed == False` so the next call retries them.
    """
    try:
        client = GeminiClient()
    except GeminiClientError as exc:
        # Missing/invalid API key — a config problem, not a runtime one.
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    service = EnrichmentService(gemini_client=client)

    try:
        result = service.run()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return EnrichResponse(
        processed=result.processed, failed=result.failed, skipped=result.skipped
    )
