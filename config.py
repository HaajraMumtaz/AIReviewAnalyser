"""
config.py

Central configuration for PointPulse AI.

Responsibilities:
    - Load environment variables (.env) for credentials and API keys.
    - Define the controlled product-category vocabulary used to
      canonicalize freeform product mentions extracted by Gemini.
    - Define the locked, deterministic formula constants for the
      Evidence Weight score and the Business Impact Score, exposed as
      plain dictionaries so downstream analytics modules can import
      them without re-deriving or hardcoding values in multiple places.

This module intentionally contains no business logic beyond simple
env parsing/coercion — it is a constants/config layer only.
"""

from __future__ import annotations

import os
from typing import Final, List

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Environment bootstrap
# ---------------------------------------------------------------------------
# Loads variables from a local .env file (if present) into os.environ.
# In deployed environments (e.g. Streamlit Community Cloud) these values
# are expected to be provided via st.secrets / platform env vars instead,
# and load_dotenv() is a safe no-op if no .env file exists.
load_dotenv()


def _get_env(name: str, default: str | None = None, required: bool = False) -> str:
    """
    Fetch an environment variable with optional default and required check.

    Args:
        name: Environment variable name.
        default: Value to fall back to if the variable is unset.
        required: If True, raises a RuntimeError when the resolved value
            is empty/None. Use this for values that MUST be present for
            the application to function (e.g. API keys in production),
            while still allowing local scaffolding to import this module
            without crashing when required=False.

    Returns:
        The resolved string value.

    Raises:
        RuntimeError: If required=True and no value could be resolved.
    """
    value = os.environ.get(name, default)
    if required and not value:
        raise RuntimeError(
            f"Missing required environment variable '{name}'. "
            f"Set it in your .env file or platform secrets."
        )
    return value or ""


# ---------------------------------------------------------------------------
# Environment variables
# ---------------------------------------------------------------------------

# Gemini API key. Not marked required=True at import time so that
# non-AI modules (e.g. the storage layer, seed script) can be imported
# and used independently without needing this configured yet.
GEMINI_API_KEY: Final[str] = _get_env("GEMINI_API_KEY", default="", required=False)

# The Google Sheets spreadsheet ID (the long ID segment in the sheet URL).
GOOGLE_SHEETS_ID: Final[str] = _get_env("GOOGLE_SHEETS_ID", default="", required=False)

# Path to the service account JSON credentials file. Defaults to a local
# "credentials.json" in the project root if not explicitly set. This value
# may also be a raw JSON string (handled by GoogleSheetsClient), which is
# useful for platforms where only environment variables are available.
GOOGLE_SERVICE_ACCOUNT_JSON_PATH: Final[str] = _get_env(
    "GOOGLE_SERVICE_ACCOUNT_JSON_PATH", default="credentials.json", required=False
)

# Gemini model identifier used across the AI layer (kept here so it is
# changed in exactly one place).
GEMINI_MODEL_NAME: Final[str] = _get_env("GEMINI_MODEL_NAME", default="gemini-1.5-flash", required=False)


# ---------------------------------------------------------------------------
# Controlled product-category vocabulary
# ---------------------------------------------------------------------------
# Used by the enrichment/canonicalization step to map freeform product
# strings returned by Gemini (e.g. "pepperoni pizza") down to a stable
# superclass (e.g. "pizza") for reliable groupby/analytics, while the
# original specific string is preserved separately as `product_raw`.
PRODUCT_CATEGORIES: Final[List[str]] = [
    "pizza",
    "burger",
    "pasta",
    "salad",
    "dessert",
    "coffee",
    "tea",
    "sandwich",
    "drink",
    "seafood",
    "breakfast",
    "appetizer",
    "steak",
    "other",
]


# ---------------------------------------------------------------------------
# Evidence Weight formula configuration (locked, see tasks.md decision #3)
# ---------------------------------------------------------------------------
# EW = clip(
#     base_score
#     + length_score(word_count)
#     + (photo_bonus if photos else 0)
#     + (specificity_bonus if has_specific_details else 0)
#     + (product_bonus if products else 0)
#     + (balance_bonus if positive_points AND issue else 0),
#     min=0, max=10
# )
EVIDENCE_WEIGHT_CONFIG: Final[dict] = {
    "base_score": 0.8,
    # Ordered smallest-to-largest; each tuple is (max_word_count_inclusive, score).
    # A word count greater than the last threshold's max falls through to
    # "length_score_default".
    "length_thresholds": [
        (3, 0.3),    # 1-3 words
        (10, 1.0),   # 4-10 words
        (25, 2.0),   # 11-25 words
    ],
    "length_score_default": 3.0,  # 26+ words
    "photo_bonus": 3.0,
    "specificity_bonus": 3.5,
    "product_bonus": 1.0,
    "balance_bonus": 0.7,
    "min_score": 0.0,
    "max_score": 10.0,
}


# ---------------------------------------------------------------------------
# Business Impact Score configuration (locked, see tasks.md decision #4)
# ---------------------------------------------------------------------------
# Score = 100 * (
#     weights["frequency"]    * freq_norm
#   + weights["neg_sentiment"] * neg_sentiment_norm
#   + weights["evidence"]      * evidence_norm
#   + weights["rating_penalty"]* rating_penalty_norm
# )
# All four *_norm terms are expected to already be normalized to [0, 1]
# by the analytics layer before this weighting is applied.
BUSINESS_IMPACT_WEIGHTS: Final[dict] = {
    "frequency": 0.35,
    "neg_sentiment": 0.30,
    "evidence": 0.20,
    "rating_penalty": 0.15,
}

# Maximum possible spread between average ratings on a 1-5 star scale,
# used to normalize the rating_penalty term to [0, 1].
BUSINESS_IMPACT_MAX_RATING_SPREAD: Final[float] = 4.0


# ---------------------------------------------------------------------------
# Meal period bucketing (locked, see tasks.md decision #1)
# ---------------------------------------------------------------------------
# Boundaries are expressed as (start_hour_inclusive, end_hour_exclusive, label),
# evaluated against a review's local "time" column (HH:MM, 24h format).
MEAL_PERIOD_BUCKETS: Final[list] = [
    (0, 11, "Morning"),
    (11, 16, "Noon"),
    (16, 19, "Evening"),
    (19, 24, "Night"),
]