"""
src/api/analytics_router.py

Phase 2 subtask 8 — Analytics API Router.

Exposes the deterministic execution pipeline via a REST endpoint.
Loads data from local CSV storage, executes the orchestration engine,
and serves the complete AnalyticsResult matrix.
"""

from __future__ import annotations

import logging
import os
from typing import List

from fastapi import APIRouter, HTTPException, status
import pandas as pd

from src.analytics.engine import AnalyticsEngine
from src.models.schema import AnalyticsResult, EnrichedReview, InstagramPost

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Analytics"])

# Default paths matching project conventions
DEFAULT_ENRICHED_PATH = os.getenv("ENRICHED_REVIEWS_CSV_PATH", "data/enriched_reviews.csv")
DEFAULT_INSTAGRAM_PATH = os.getenv("INSTAGRAM_CSV_PATH", "data/instagram.csv")


def _load_enriched_reviews(path: str) -> List[EnrichedReview]:
    if not os.path.exists(path):
        logger.warning("Enriched reviews file not found at %s. Returning empty list.", path)
        return []
    
    try:
        df = pd.read_csv(path).fillna("")
        reviews = []
        for _, row in df.iterrows():
            row_dict = row.to_dict()
            # Reconstruct list fields that were joined by semicolons during enrichment
            if isinstance(row_dict.get("products"), str):
                row_dict["products"] = [p.strip() for p in row_dict["products"].split(";") if p.strip()]
            if isinstance(row_dict.get("brand_attributes"), str):
                row_dict["brand_attributes"] = [b.strip() for b in row_dict["brand_attributes"].split(";") if b.strip()]
            if isinstance(row_dict.get("positive_points"), str):
                row_dict["positive_points"] = [p.strip() for p in row_dict["positive_points"].split(";") if p.strip()]
                
            reviews.append(EnrichedReview.model_validate(row_dict))
        return reviews
    except Exception as e:
        logger.error("Failed to parse enriched reviews CSV: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading enriched reviews data: {str(e)}"
        )


def _load_instagram_posts(path: str) -> List[InstagramPost]:
    if not os.path.exists(path):
        logger.warning("Instagram marketing file not found at %s. Returning empty list.", path)
        return []
    
    try:
        df = pd.read_csv(path).fillna("")
        posts = []
        for _, row in df.iterrows():
            row_dict = row.to_dict()
            if isinstance(row_dict.get("hashtags"), str):
                row_dict["hashtags"] = [t.strip() for t in row_dict["hashtags"].split(";") if t.strip()]
                
            posts.append(InstagramPost.model_validate(row_dict))
        return posts
    except Exception as e:
        logger.error("Failed to parse Instagram marketing CSV: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading Instagram data: {str(e)}"
        )


@router.post("/analyze", response_model=AnalyticsResult, status_code=status.HTTP_200_OK)
def analyze_cafe_data() -> AnalyticsResult:
    """
    Synchronously ingest local data collections and trigger the
    deterministic execution sequence.
    
    Returns a unified payload containing pattern mappings, performance arrays,
    and platform delivery delta gaps.
    """
    logger.info("Initiating Phase 2 analytics orchestration run.")
    
    reviews = _load_enriched_reviews(DEFAULT_ENRICHED_PATH)
    instagram_posts = _load_instagram_posts(DEFAULT_INSTAGRAM_PATH)
    
    if not reviews:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No processed data payload found. Run Phase 1 review enrichment first."
        )
        
    engine = AnalyticsEngine()
    result = engine.run(reviews=reviews, instagram_posts=instagram_posts)
    
    logger.info("Analytics run compiled successfully.")
    return result