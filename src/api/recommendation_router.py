"""
src/api/recommendation_router.py

Phase 3 API surface.

POST /api/recommend
    Input:  AnalyticsResult (already computed, deterministic Phase 2 output)
    Output: ExecutiveActionCenter
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, status

from src.ai.gemini_client import GeminiClient, GeminiClientError
from src.models.schema import AnalyticsResult, ExecutiveActionCenter
from src.services.recommendation_service import (
    RecommendationService,
    RecommendationServiceError,
)

router = APIRouter(prefix="/api", tags=["recommendations"])


@lru_cache(maxsize=1)
def _get_gemini_client() -> GeminiClient:
    return GeminiClient()


def get_recommendation_service(
    gemini_client: GeminiClient = Depends(_get_gemini_client),
) -> RecommendationService:
    return RecommendationService(gemini_client=gemini_client)


@router.post(
    "/recommend",
    response_model=ExecutiveActionCenter,
    status_code=status.HTTP_200_OK,
    summary="Generate the executive action center from computed analytics",
)
def recommend(
    analytics: AnalyticsResult,
    service: RecommendationService = Depends(get_recommendation_service),
) -> ExecutiveActionCenter:
    try:
        return service.generate(analytics)
    except RecommendationServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except GeminiClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini failed to produce recommendations: {exc}",
        ) from exc