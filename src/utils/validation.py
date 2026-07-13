"""
src/utils/validation.py

Phase 1 — validates every Gemini response before it is saved.

This module owns exactly one job: turn a raw dict (whatever
`GeminiClient.enrich_review` handed back after JSON-parsing the model's
output) into a trustworthy `GeminiExtractedFields`, or raise a clear,
specific error if it can't. No enrichment orchestration, no CSV I/O,
no product normalization — that's `enrichment_service.py`'s job.
"""

from __future__ import annotations

from typing import Any, Dict

from pydantic import ValidationError

from src.models.schema import GeminiExtractedFields


class EnrichmentValidationError(Exception):
    """
    Raised when a Gemini response fails validation — either it isn't a
    JSON object at all, or it doesn't satisfy `GeminiExtractedFields`
    (bad enum value, sentiment_strength out of [0, 1], wrong types,
    etc.). Distinct from `GeminiClientError` (network/parsing failures)
    so `EnrichmentService` can tell "Gemini didn't answer" apart from
    "Gemini answered but the answer was garbage".
    """


def validate_gemini_response(raw: Dict[str, Any], *, review_id: str) -> GeminiExtractedFields:
    """
    Validate a single raw Gemini response dict.

    Args:
        raw: parsed JSON dict returned by GeminiClient.
        review_id: included in the error message only, to make failures
            traceable back to a specific row without the caller having
            to re-wrap the exception.

    Raises:
        EnrichmentValidationError: if `raw` isn't a dict, or doesn't
            satisfy the GeminiExtractedFields schema.
    """
    if not isinstance(raw, dict):
        raise EnrichmentValidationError(
            f"[{review_id}] Gemini response was not a JSON object: {type(raw).__name__}"
        )

    try:
        return GeminiExtractedFields.model_validate(raw)
    except ValidationError as exc:
        raise EnrichmentValidationError(
            f"[{review_id}] Gemini response failed schema validation: {exc}"
        ) from exc
