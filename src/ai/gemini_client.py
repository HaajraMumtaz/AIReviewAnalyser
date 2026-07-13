"""
src/ai/gemini_client.py

Thin wrapper around Gemini for PointPulse AI.

Responsibilities (per contracts.md: "Gemini is only used during
enrichment and recommendation generation"):
    - Phase 1: building the enrichment prompt, calling Gemini, parsing
      the response as JSON (`enrich_review` / `enrich_reviews_batch`).
    - Phase 3: building the executive recommendation prompt, calling
      Gemini, parsing the response as JSON (`generate_executive_recommendations`).

`GeminiClient` intentionally returns raw `dict`s, never validated
models — schema validation is the caller's job (`validate_gemini_response`
for Phase 1, `RecommendationService` for Phase 3). This keeps
`GeminiClient` importable/mockable without pulling in the rest of the
Pydantic model graph.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_MODEL_NAME = "gemini-1.5-flash"
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 2.0

# Phase 3 uses a stronger model by default — executive narrative
# generation benefits from better reasoning than per-review enrichment,
# which runs at much higher volume and needs to stay cheap/fast.
DEFAULT_RECOMMENDATION_MODEL_NAME = "gemini-1.5-pro"
DEFAULT_BATCH_SIZE = 10
# The exact 8 fields Gemini is allowed to return (architecture.md
# "Gemini Fields"). Kept as a module constant so the prompt and
# GeminiExtractedFields can be visually cross-checked against each other.
ENRICHMENT_SYSTEM_PROMPT = """You are a restaurant review analyst for PointPulse AI.

You will be given one customer review and its star rating. Extract
ONLY the following fields and return them as a single, valid JSON
object — no markdown fences, no commentary, no extra keys.

Fields:
- "sentiment": one of "positive", "neutral", "negative" — the overall
  tone of the review, not just the star rating.
- "sentiment_strength": a number from 0.0 to 1.0, how strongly that
  sentiment is expressed (mild remark vs. emphatic praise/complaint).
- "department": the operational area most responsible for what the
  review is about, in a short lowercase phrase (e.g. "kitchen",
  "delivery", "front of house", "facilities", "pricing"). Pick the
  single most relevant department even if the review touches more
  than one area.
- "issue": a short lowercase snake_case label for the single
  PRIMARY complaint in the review (e.g. "slow_delivery",
  "cold_food", "rude_staff", "overpriced", "parking_difficulty").
  If the review has no complaint at all, use null.
- "products": a list of specific food/drink items the review
  mentions by name, exactly as worded in the review (e.g.
  ["pepperoni pizza", "spanish latte"]). Empty list if none.
- "brand_attributes": short phrases describing the venue/brand
  itself that the review praises or criticizes, NOT food items
  (e.g. "cozy lighting", "pet friendly", "generator backup",
  "prayer room"). Empty list if none.
- "positive_points": short phrases capturing what the reviewer
  specifically liked, if anything, even in an otherwise negative
  review. Empty list if none.
- "has_specific_details": true if the review contains a concrete,
  checkable detail (a specific wait time, price, staff name, dish
  name, etc.) rather than only vague sentiment; false otherwise.

Rules:
- "issue" is singular: pick the one complaint most central to the
  review, even if multiple are mentioned.
- Base "sentiment" on the review text, not only the star rating —
  a 3-star review can read as clearly negative or clearly positive.
- Return valid JSON only. Do not wrap it in ```json fences.
"""

_FEW_SHOT_EXAMPLE_REVIEW = (
    'Review (rating 2/5): "Service was slow despite the place not being busy. '
    'Waited 45 mins for a single smash burger and it was dripping oil."'
)
_FEW_SHOT_EXAMPLE_RESPONSE = json.dumps(
    {
        "sentiment": "negative",
        "sentiment_strength": 0.75,
        "department": "kitchen",
        "issue": "slow_service",
        "products": ["smash burger"],
        "brand_attributes": [],
        "positive_points": [],
        "has_specific_details": True,
    }
)

# ---------------------------------------------------------------------
# Phase 3 — Executive Recommendation prompt
# ---------------------------------------------------------------------

EXECUTIVE_SYSTEM_PROMPT = """You are a restaurant operations consultant writing an executive action \
briefing for a café's leadership team (owner, GM, and shift leads). You \
speak fluent café-operations terminology: throughput, ticket times, \
covers, rush-hour bottlenecks, station calibration, mise en place, and \
guest recovery. You are given ONLY pre-computed analytics summaries — \
never raw customer reviews — and your job is to turn those numbers into \
sharp, decision-ready narrative copy.

Rules:
- Never invent facts, numbers, or issues not present in the supplied data.
- Ground every sentence in the specific numbers/labels given to you.
- Write in a direct, executive-briefing tone: no filler, no hedging.
- Action items must be concrete and operational (who does what, at what \
station, during which service window) — not generic advice.
- Return ONLY valid JSON matching the required schema. No markdown \
fences, no commentary outside the JSON object.
"""

_EXECUTIVE_RESPONSE_SHAPE = """{
  "operational_priority": {
    "headline": str,
    "impact_analysis": str,       // 2-4 sentences, cite the numbers given
    "action_plan": [str, ...]     // 3-5 concrete operational steps
  },
  "rating_driver": {
    "headline": str,
    "friction_analysis": str,     // 2-4 sentences, cite the rating delta
    "mitigation_steps": [str, ...] // 3-5 concrete steps
  },
  "marketing_opportunity": {
    "headline": str,
    "angle_analysis": str,
    "campaign_ideas": [str, ...]  // 3-5 ideas
  } or null if no marketing opportunity data was supplied,
  "hidden_gem": {
    "headline": str,
    "discovery_analysis": str,
    "activation_plan": [str, ...] // 3-5 steps
  } or null if no hidden gem data was supplied
}"""


class GeminiClientError(Exception):
    """
    Raised when a Gemini API call fails after all retries are
    exhausted, or when the response text can't be parsed as JSON at
    all. Schema-level problems (wrong types, invalid enum values) are
    NOT raised here — those surface downstream once this class has
    successfully handed back a dict (`validate_gemini_response` for
    Phase 1, Pydantic `model_validate` inside `RecommendationService`
    for Phase 3).
    """


class GeminiClient:
    """
    Usage:
        client = GeminiClient()  # reads GEMINI_API_KEY from the environment
        raw = client.enrich_review(review_text, rating)   # -> dict
        raw = client.generate_executive_recommendations(summary)  # -> dict
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        recommendation_model_name: Optional[str] = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_backoff_seconds: float = DEFAULT_RETRY_BACKOFF_SECONDS,
            batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
    
        self.batch_size = batch_size
    
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise GeminiClientError(
                "GEMINI_API_KEY is not set. Add it to your .env file or pass "
                "api_key= explicitly."
            )

        self.model_name = model_name or os.getenv("GEMINI_MODEL", DEFAULT_MODEL_NAME)
        self.recommendation_model_name = recommendation_model_name or os.getenv(
            "GEMINI_RECOMMENDATION_MODEL", DEFAULT_RECOMMENDATION_MODEL_NAME
        )
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self._client = self._build_client()

    def _build_client(self):
        # Imported lazily so unit tests can construct a GeminiClient
        # subclass / monkeypatch this method without google-genai being
        # importable in the test environment. Uses the current Google
        # Gen AI SDK (`google-genai` / `from google import genai`) —
        # the older `google-generativeai` package is deprecated.
        from google import genai

        return genai.Client(api_key=self.api_key)

    # -------------------------------------------------------------
    # Phase 1 — Enrichment
    # -------------------------------------------------------------

    def enrich_review(self, review_text: str, rating: int) -> Dict[str, Any]:
        """
        Enrich a single review. Returns the parsed JSON dict as-is —
        UNVALIDATED. Callers must run this through
        `validate_gemini_response` before trusting it.

        Raises:
            GeminiClientError: if every retry attempt fails, or the
                final response text isn't valid JSON.
        """
        prompt = self._build_enrichment_prompt(review_text, rating)
        return self._generate_json_with_retries(
            model_name=self.model_name,
            system_prompt=ENRICHMENT_SYSTEM_PROMPT,
            user_prompt=prompt,
            temperature=0.2,
            error_context="Gemini enrichment",
        )

    def enrich_reviews_batch(
    self,
    reviews: List[Any],
    ) -> List[Dict[str, Any]]:
        """
        Enrich reviews in batches of `self.batch_size`.

        Returns:
            [
                {
                    "review_id": "...",
                    "data": {...} | None,
                    "error": str | None,
                }
            ]
        """
        results: List[Dict[str, Any]] = []

        for start in range(0, len(reviews), self.batch_size):
            batch = reviews[start:start + self.batch_size]

            try:
                response = self._generate_batch(batch)

                if len(response) != len(batch):
                    raise GeminiClientError(
                        f"Expected {len(batch)} results, got {len(response)}"
                    )

                for review, data in zip(batch, response):
                    results.append(
                        {
                            "review_id": review.review_id,
                            "data": data,
                            "error": None,
                        }
                    )

            except Exception as exc:
                logger.exception("Batch enrichment failed")

                for review in batch:
                    results.append(
                        {
                            "review_id": review.review_id,
                            "data": None,
                            "error": str(exc),
                        }
                    )

        return results
    @staticmethod
    def _build_enrichment_prompt(review_text: str, rating: int) -> str:
        return (
            f"Example:\n{_FEW_SHOT_EXAMPLE_REVIEW}\n"
            f"Example response:\n{_FEW_SHOT_EXAMPLE_RESPONSE}\n\n"
            f'Now extract the fields for this review:\n'
            f'Review (rating {rating}/5): "{review_text}"'
        )

    # -------------------------------------------------------------
    # Phase 3 — Executive Recommendations
    # -------------------------------------------------------------

    def generate_executive_recommendations(
        self, analytics_summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Given a JSON-serializable summary of the top computed analytics
        items (business impact, rating driver, marketing gap, hidden
        gem — see `RecommendationService._build_analytics_summary`),
        ask Gemini to produce executive narrative copy for all four
        slots in a single call.

        Returns the parsed JSON dict as-is — UNVALIDATED. The caller
        (`RecommendationService`) is responsible for validating this
        against the internal narrative Pydantic models before merging
        it with the deterministic analytics fields.

        Raises:
            GeminiClientError: if every retry attempt fails, or the
                final response text isn't valid JSON.
        """
        prompt = self._build_executive_prompt(analytics_summary)
        return self._generate_json_with_retries(
            model_name=self.recommendation_model_name,
            system_prompt=EXECUTIVE_SYSTEM_PROMPT,
            user_prompt=prompt,
            temperature=0.3,
            error_context="Gemini executive recommendation generation",
        )

    @staticmethod
    def _build_executive_prompt(analytics_summary: Dict[str, Any]) -> str:
        return (
            "Here is the pre-computed analytics data for this cycle:\n\n"
            f"{json.dumps(analytics_summary, indent=2, default=str)}\n\n"
            "Using ONLY the data above, produce an executive narrative "
            "bundle matching this exact JSON shape:\n"
            f"{_EXECUTIVE_RESPONSE_SHAPE}"
        )

    # -------------------------------------------------------------
    # Shared internals
    # -------------------------------------------------------------

    def _generate_json_with_retries(
        self,
        *,
        model_name: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        error_context: str,
    ) -> Dict[str, Any]:
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._generate(
                    model_name=model_name,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                )
                return self._parse_json(response.text)
            except GeminiClientError:
                # JSON parse failures are worth retrying too — Gemini
                # occasionally emits malformed JSON on a bad sample.
                raise
            except Exception as exc:  # noqa: BLE001 — deliberately broad: any
                # SDK/network error should trigger a retry, not crash the batch.
                last_error = exc
                logger.warning(
                    "%s attempt %d/%d failed: %s",
                    error_context,
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff_seconds * attempt)

        raise GeminiClientError(
            f"{error_context} failed after {self.max_retries} attempts: {last_error}"
        )

    def _generate(self, prompt: str):
        from google.genai import types

        return self._client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=ENRICHMENT_SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
    @staticmethod
    def _parse_json(text: str) -> Dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise GeminiClientError(
                f"Could not parse Gemini response as JSON: {exc}\n"
                f"Raw response (truncated): {text[:500]!r}"
            ) from exc
    @staticmethod
    def _build_batch_prompt(reviews: List[Any]) -> str:
        lines = [
            "Extract the required fields for EACH review.",
            "Return ONLY a JSON array.",
            "The array length MUST equal the number of reviews.",
            "",
        ]

        for i, review in enumerate(reviews, start=1):
            lines.append(
                f'{i}. Rating {review.rating}/5\nReview: "{review.review}"'
            )

        return "\n\n".join(lines)
    def _generate_batch(self, reviews: List[Any]) -> List[Dict[str, Any]]:
        prompt = self._build_batch_prompt(reviews)

        response = self._generate(prompt)

        data = self._parse_json(response.text)

        if not isinstance(data, list):
            raise GeminiClientError("Gemini returned non-list response")

        return data