"""
src/services/enrichment_service.py

Phase 1 — the enrichment pipeline itself:

    load reviews
        -> filter processed == FALSE
        -> Gemini enrichment
        -> validate
        -> product normalization
        -> meal period
        -> evidence weight
        -> mark processed
        -> save

No analytics or dashboard logic lives here — only what's needed to
turn RawReview rows into EnrichedReview rows and persist both files.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional, Tuple

import pandas as pd
from pydantic import BaseModel, Field

from src.ai.gemini_client import GeminiClient, GeminiClientError
from src.models.schema import (
    EnrichedReview,
    MealPeriod,
    ProductCategory,
    RawReview,
)
from src.storage.schema import ReviewsSchema as RS
from src.utils.validation import EnrichmentValidationError, validate_gemini_response

logger = logging.getLogger(__name__)

DEFAULT_REVIEWS_PATH = os.getenv("REVIEWS_CSV_PATH", "data/reviews.csv")
DEFAULT_ENRICHED_PATH = os.getenv("ENRICHED_REVIEWS_CSV_PATH", "data/enriched_reviews.csv")

# ---------------------------------------------------------------------------
# Deterministic product canonicalization (Python, not AI — architecture.md
# "Stage 3 — AI Review Enrichment" -> product_category is Python-computed).
# Checked in list order; first match wins. Updated for specialty coffee menu.
# ---------------------------------------------------------------------------

PRODUCT_KEYWORDS: List[Tuple[ProductCategory, List[str]]] = [
    (
        ProductCategory.COLD_COFFEE,
        [
            "iced americano", "iced latte", "iced spanish", "iced cappuccino",
            "iced hazelnut", "iced vanilla", "iced caramel", "iced dark mocca",
            "iced pistachio", "iced hazelnut machiatto", "iced"
        ],
    ),
    (
        ProductCategory.FRAPPE,
        ["frappicino", "frappuccino", "kinder", "lotus biscoff", "oreo", "mocca"],
    ),
    (ProductCategory.MATCHA, ["matcha"]),
    (ProductCategory.ICED_TEA, ["iced tea", "lychee", "peach"]),
    (ProductCategory.SMOOTHIE, ["smoothie", "pineapple banana", "mixed berry"]),
    (
        ProductCategory.SPECIALTY_COFFEE,
        [
            "espresso", "machiatto", "cortado", "piccolo", "flat white",
            "afogato", "cold brew", "pour over", "v60", "aeropress"
        ],
    ),
    (
        ProductCategory.HOT_COFFEE,
        [
            "honey latte", "dark mocca", "spanish latte", "hazelnut latte",
            "vanilla latte", "caramel latte", "tiramissu", "pistachio latte",
            "hot chocolate", "point tea", "latte", "cappuccino", "americano"
        ],
    ),
    (
        ProductCategory.ADD_ON,
        ["upsize", "cold foam", "flavour shot", "extra shot", "sparkling water"]
    ),
]


def normalize_products(products: List[str]) -> Tuple[Optional[str], Optional[ProductCategory]]:
    """
    Deterministically map Gemini's freeform `products` mentions onto
    (product_raw, product_category).

    - product_raw: the raw mentions joined for display/audit, or None
      if Gemini extracted no products at all.
    - product_category: the first ProductCategory whose keywords match
      any mention (case-insensitive substring match), OTHER if there
      were mentions but none matched a keyword, or None if there were
      no mentions to categorize in the first place.
    """
    if not products:
        return None, None

    product_raw = ", ".join(products)
    haystack = product_raw.lower()

    for category, keywords in PRODUCT_KEYWORDS:
        if any(keyword in haystack for keyword in keywords):
            return product_raw, category

    return product_raw, ProductCategory.OTHER


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class EnrichmentFailure(BaseModel):
    review_id: str
    error: str


class EnrichmentResult(BaseModel):
    processed: int = 0
    failed: List[EnrichmentFailure] = Field(default_factory=list)
    skipped: int = 0


class EnrichmentService:
    """
    Orchestrates one end-to-end enrichment run over `reviews.csv`,
    writing results to `enriched_reviews.csv` and flipping `processed`
    back to True in `reviews.csv` for every row that succeeded.

    Rows that fail (Gemini error or validation error) are left with
    `processed == False` so the next run retries them automatically.
    """

    def __init__(
        self,
        gemini_client: GeminiClient,
        reviews_path: str = DEFAULT_REVIEWS_PATH,
        enriched_path: str = DEFAULT_ENRICHED_PATH,
    ) -> None:
        self.gemini_client = gemini_client
        self.reviews_path = reviews_path
        self.enriched_path = enriched_path

    # -- public API ----------------------------------------------------

    def run(self) -> EnrichmentResult:
        if not os.path.exists(self.reviews_path):
                raise FileNotFoundError(
                    f"Reviews file not found: {self.reviews_path}"
                )

        reviews_df = self._read_reviews()
        enriched_rows_by_id = self._read_enriched_rows()

        result = EnrichmentResult()

        updated_raw_rows: List[dict] = []
        pending_reviews: List[RawReview] = []
        pending_row_dicts: Dict[str, dict] = {}

        # Collect pending reviews
        for _, raw_row in reviews_df.iterrows():

            row_dict = raw_row.to_dict()
            raw_review = RawReview.model_validate(row_dict)

            updated_raw_rows.append(row_dict)

            if raw_review.processed:
                result.skipped += 1
                continue

            pending_reviews.append(raw_review)
            pending_row_dicts[raw_review.review_id] = row_dict

        # Nothing to enrich
        if not pending_reviews:
            self._write_reviews(updated_raw_rows)
            self._write_enriched(enriched_rows_by_id)
            return result

        batch_results = self.gemini_client.enrich_reviews_batch(
            pending_reviews
        )

        raw_lookup = {
            r.review_id: r
            for r in pending_reviews
        }

        for item in batch_results:

            review_id = item["review_id"]

            if item["error"] is not None:
                logger.error(
                    "Enrichment failed for %s: %s",
                    review_id,
                    item["error"],
                )
                result.failed.append(
                    EnrichmentFailure(
                        review_id=review_id,
                        error=item["error"],
                    )
                )
                continue

            raw_review = raw_lookup[review_id]

            try:
                enriched = self._build_enriched_review(
                    raw_review,
                    item["data"],
                )

                enriched_rows_by_id[
                    review_id
                ] = self._enriched_to_row(enriched)

                pending_row_dicts[review_id][RS.PROCESSED] = True

                result.processed += 1

            except EnrichmentValidationError as exc:
                logger.error(
                    "Validation failed for %s: %s",
                    review_id,
                    exc,
                )

                result.failed.append(
                    EnrichmentFailure(
                        review_id=review_id,
                        error=str(exc),
                    )
                )

        self._write_reviews(updated_raw_rows)
        self._write_enriched(enriched_rows_by_id)

        return result
    # -- pipeline steps --------------------------------------------------


    def _build_enriched_review(
        self,
        raw: RawReview,
        ai_response: dict,
    ) -> EnrichedReview:

        ai_fields = validate_gemini_response(
            ai_response,
            review_id=raw.review_id,
        )

        product_raw, product_category = normalize_products(
            ai_fields.products
        )

        meal_period = MealPeriod.from_time(raw.time)

        evidence_weight = EnrichedReview.compute_evidence_weight(
            word_count=raw.word_count,
            has_photos=raw.photos,
            has_specific_details=ai_fields.has_specific_details,
            has_products=bool(ai_fields.products),
            has_positive_points=bool(ai_fields.positive_points),
            has_issue=bool(ai_fields.issue),
        )

        return EnrichedReview(
            review_id=raw.review_id,
            review=raw.review,
            rating=raw.rating,
            date=raw.date,
            time=raw.time,
            source=raw.source,
            photos=raw.photos,
            processed=True,
            sentiment=ai_fields.sentiment,
            sentiment_strength=ai_fields.sentiment_strength,
            department=ai_fields.department,
            issue=ai_fields.issue,
            products=ai_fields.products,
            product_raw=product_raw,
            product_category=product_category,
            brand_attributes=ai_fields.brand_attributes,
            positive_points=ai_fields.positive_points,
            has_specific_details=ai_fields.has_specific_details,
            evidence_weight=evidence_weight,
            persisted_meal_period=meal_period,
        )

        # -- CSV I/O ----------------------------------------------------------

    def _read_reviews(self) -> pd.DataFrame:
        return pd.read_csv(self.reviews_path, dtype=str).fillna("")

    def _read_enriched_rows(self) -> Dict[str, dict]:
        """Load any already-enriched rows, keyed by review_id, for upsert."""
        if not os.path.exists(self.enriched_path):
            return {}
        df = pd.read_csv(self.enriched_path, dtype=str).fillna("")
        return {row[RS.REVIEW_ID]: row.to_dict() for _, row in df.iterrows()}

    def _write_reviews(self, rows: List[dict]) -> None:
        df = pd.DataFrame(rows, columns=RS.RAW_COLUMNS)
        df.to_csv(self.reviews_path, index=False)

    def _write_enriched(self, rows_by_id: Dict[str, dict]) -> None:
        os.makedirs(os.path.dirname(self.enriched_path) or ".", exist_ok=True)
        df = pd.DataFrame(list(rows_by_id.values()), columns=RS.COLUMNS)
        df.to_csv(self.enriched_path, index=False)

    @staticmethod
    def _enriched_to_row(enriched: EnrichedReview) -> dict:
        """Flatten an EnrichedReview into a CSV-ready row keyed by column name."""
        return {
            RS.REVIEW_ID: enriched.review_id,
            RS.REVIEW: enriched.review,
            RS.RATING: enriched.rating,
            RS.DATE: enriched.date.isoformat(),
            RS.TIME: enriched.time.strftime("%H:%M") if enriched.time else "",
            RS.SOURCE: enriched.source.value,
            RS.PHOTOS: enriched.photos,
            RS.PROCESSED: enriched.processed,
            RS.SENTIMENT: enriched.sentiment.value,
            RS.SENTIMENT_STRENGTH: enriched.sentiment_strength,
            RS.DEPARTMENT: enriched.department,
            RS.ISSUE: enriched.issue or "",
            RS.PRODUCTS: "; ".join(enriched.products),
            RS.PRODUCT_RAW: enriched.product_raw or "",
            RS.PRODUCT_CATEGORY: enriched.product_category.value
            if enriched.product_category
            else "",
            RS.BRAND_ATTRIBUTES: "; ".join(enriched.brand_attributes),
            RS.POSITIVE_POINTS: "; ".join(enriched.positive_points),
            RS.HAS_SPECIFIC_DETAILS: enriched.has_specific_details,
            RS.EVIDENCE_WEIGHT: enriched.evidence_weight,
            RS.MEAL_PERIOD: enriched.persisted_meal_period.value
            if enriched.persisted_meal_period
            else "",
        }