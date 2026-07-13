"""
src/storage/schema.py

Single source of truth for Google Sheets column names and sheet-tab
names. No other module should hardcode a sheet name or column string —
they should import the constants defined here instead. This keeps the
storage layer, ETL pipeline, analytics engine, and seed script from
silently drifting out of sync with each other.

Two sheets are modeled:
    - ReviewsSchema:   the "Reviews" tab (raw + AI-enriched + computed columns)
    - InstagramSchema: the "Instagram" tab (raw caption data)
"""

from __future__ import annotations

from typing import Final, List


class ReviewsSchema:
    """
    Column layout for the "Reviews" sheet tab.

    Columns are grouped into three logical categories, though all are
    stored as flat columns in the same sheet row:

    1. Raw input columns   - populated at data-collection time (Stage 1).
    2. Pipeline columns    - the incremental-processing flag (Stage 2).
    3. Enriched columns    - populated by Gemini enrichment + deterministic
                              post-processing (Stage 3 / Phase 3-4), left
                              blank until a row has been processed.
    """

    SHEET_NAME: Final[str] = "Reviews"

    # --- Raw input columns (Stage 1) ---------------------------------
    REVIEW_ID: Final[str] = "review_id"
    REVIEW: Final[str] = "review"
    RATING: Final[str] = "rating"
    DATE: Final[str] = "date"
    TIME: Final[str] = "time"  # HH:MM, 24h format; powers meal-period bucketing
    SOURCE: Final[str] = "source"
    PHOTOS: Final[str] = "photos"

    # --- Pipeline / incremental-processing column (Stage 2) ----------
    PROCESSED: Final[str] = "processed"

    # --- AI-enriched columns (Stage 3, written back by the ETL pipeline) ---
    SENTIMENT: Final[str] = "sentiment"
    SENTIMENT_STRENGTH: Final[str] = "sentiment_strength"
    DEPARTMENT: Final[str] = "department"
    ISSUE: Final[str] = "issue"
    PRODUCTS: Final[str] = "products"
    PRODUCT_RAW: Final[str] = "product_raw"
    PRODUCT_CATEGORY: Final[str] = "product_category"
    BRAND_ATTRIBUTES: Final[str] = "brand_attributes"
    POSITIVE_POINTS: Final[str] = "positive_points"
    HAS_SPECIFIC_DETAILS: Final[str] = "has_specific_details"

    # --- Deterministic computed columns (Phase 4-5) -------------------
    EVIDENCE_WEIGHT: Final[str] = "evidence_weight"
    MEAL_PERIOD: Final[str] = "meal_period"

    # Full column order as written to row 1 (the header row) of the sheet.
    COLUMNS: Final[List[str]] = [
        REVIEW_ID,
        REVIEW,
        RATING,
        DATE,
        TIME,
        SOURCE,
        PHOTOS,
        PROCESSED,
        SENTIMENT,
        SENTIMENT_STRENGTH,
        DEPARTMENT,
        ISSUE,
        PRODUCTS,
        PRODUCT_RAW,
        PRODUCT_CATEGORY,
        BRAND_ATTRIBUTES,
        POSITIVE_POINTS,
        HAS_SPECIFIC_DETAILS,
        EVIDENCE_WEIGHT,
        MEAL_PERIOD,
    ]

    # Columns that must be present on every row at collection time
    # (i.e. before any enrichment has taken place).
    RAW_COLUMNS: Final[List[str]] = [
        REVIEW_ID,
        REVIEW,
        RATING,
        DATE,
        TIME,
        SOURCE,
        PHOTOS,
        PROCESSED,
    ]

    # Columns populated only after successful enrichment.
    ENRICHED_COLUMNS: Final[List[str]] = [
        SENTIMENT,
        SENTIMENT_STRENGTH,
        DEPARTMENT,
        ISSUE,
        PRODUCTS,
        PRODUCT_RAW,
        PRODUCT_CATEGORY,
        BRAND_ATTRIBUTES,
        POSITIVE_POINTS,
        HAS_SPECIFIC_DETAILS,
        EVIDENCE_WEIGHT,
        MEAL_PERIOD,
    ]


class InstagramSchema:
    """Column layout for the "Instagram" sheet tab (raw caption data)."""

    SHEET_NAME: Final[str] = "Instagram"

    CAPTION_ID: Final[str] = "caption_id"
    CAPTION: Final[str] = "caption"
    DATE: Final[str] = "date"
    CAMPAIGN: Final[str] = "campaign"

    COLUMNS: Final[List[str]] = [
        CAPTION_ID,
        CAPTION,
        DATE,
        CAMPAIGN,
    ]