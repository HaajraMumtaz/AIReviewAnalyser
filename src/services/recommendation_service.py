"""
src/services/recommendation_service.py

Phase 3 — Executive Recommendation Engine.

Converts a fully-computed, deterministic AnalyticsResult into an
ExecutiveActionCenter. Gemini NEVER sees raw reviews here — it only
ever receives a JSON summary of the already-computed analytics (top
business impact issue, top rating driver, top marketing gap, top
hidden gem) and is asked to produce executive-facing narrative copy
for them via `GeminiClient.generate_executive_recommendations`.

All numeric/categorical fields on the output models (issue, score,
rating_delta, gap_score, product_category, avg_sentiment_strength)
are copied directly from AnalyticsResult — Gemini cannot alter them.
Only the narrative fields (headline, *_analysis, action/mitigation/
campaign/activation lists) are Gemini-generated, and even those are
schema-validated before being merged into the final result.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError

from src.ai.gemini_client import GeminiClient, GeminiClientError
from src.models.schema import (
    AnalyticsResult,
    BusinessImpactScore,
    ExecutiveActionCenter,
    HiddenGem,
    HiddenGemRecommendation,
    MarketingGap,
    MarketingOpportunityRecommendation,
    OperationalPriorityRecommendation,
    RatingDriver,
    RatingDriverRecommendation,
)


class RecommendationServiceError(RuntimeError):
    """Raised when an ExecutiveActionCenter cannot be produced."""


# ---------------------------------------------------------------------
# Gemini-facing narrative schemas (internal — never exposed via API)
# ---------------------------------------------------------------------


class _OperationalNarrative(BaseModel):
    headline: str
    impact_analysis: str
    action_plan: List[str] = Field(..., min_length=3, max_length=5)


class _RatingDriverNarrative(BaseModel):
    headline: str
    friction_analysis: str
    mitigation_steps: List[str] = Field(..., min_length=3, max_length=5)


class _MarketingNarrative(BaseModel):
    headline: str
    angle_analysis: str
    campaign_ideas: List[str] = Field(..., min_length=3, max_length=5)


class _HiddenGemNarrative(BaseModel):
    headline: str
    discovery_analysis: str
    activation_plan: List[str] = Field(..., min_length=3, max_length=5)


class _ExecutiveNarrativeBundle(BaseModel):
    operational_priority: _OperationalNarrative
    rating_driver: _RatingDriverNarrative
    marketing_opportunity: Optional[_MarketingNarrative] = None
    hidden_gem: Optional[_HiddenGemNarrative] = None


# ---------------------------------------------------------------------
# Selection helpers — pick the single top item per category
# ---------------------------------------------------------------------


def _select_top_business_impact(
    analytics: AnalyticsResult,
) -> BusinessImpactScore:
    if not analytics.business_impact:
        raise RecommendationServiceError(
            "AnalyticsResult.business_impact is empty; cannot build "
            "OperationalPriorityRecommendation."
        )
    return max(analytics.business_impact, key=lambda item: item.score)


def _select_top_rating_driver(analytics: AnalyticsResult) -> RatingDriver:
    if not analytics.rating_drivers:
        raise RecommendationServiceError(
            "AnalyticsResult.rating_drivers is empty; cannot build "
            "RatingDriverRecommendation."
        )
    return max(analytics.rating_drivers, key=lambda item: item.rating_delta)


def _select_top_marketing_gap(
    analytics: AnalyticsResult,
) -> Optional[MarketingGap]:
    underrepresented = [
        gap for gap in analytics.marketing_gap if gap.is_underrepresented
    ]
    candidates = underrepresented or list(analytics.marketing_gap)
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.gap_score)


def _select_top_hidden_gem(analytics: AnalyticsResult) -> Optional[HiddenGem]:
    if not analytics.hidden_gems:
        return None
    return max(analytics.hidden_gems, key=lambda item: item.avg_sentiment_strength)


def _build_analytics_summary(
    business_impact: BusinessImpactScore,
    rating_driver: RatingDriver,
    marketing_gap: Optional[MarketingGap],
    hidden_gem: Optional[HiddenGem],
) -> Dict[str, Any]:
    """
    Build the plain-dict summary handed to Gemini. Only pre-computed
    analytics fields go in here — never raw review text.
    """
    pattern = business_impact.pattern

    summary: Dict[str, Any] = {
        "top_operational_priority": {
            "issue": business_impact.issue,
            "business_impact_score": business_impact.score,
            "freq_norm": business_impact.freq_norm,
            "neg_sentiment_norm": business_impact.neg_sentiment_norm,
            "evidence_norm": business_impact.evidence_norm,
            "rating_penalty_norm": business_impact.rating_penalty_norm,
            "total_mentions": pattern.review_count,
            "peak_day_rush_hour_bottleneck": pattern.peak_day,
            "peak_meal_period": pattern.peak_meal_period,
            "weekend_share": pattern.weekend_share,
            "department": pattern.department,
            "products_affected": pattern.products_affected,
            "platform_breakdown": pattern.platform_breakdown,
        },
        "top_rating_driver": {
            "issue": rating_driver.issue,
            "avg_rating_with_issue": rating_driver.avg_rating_with_issue,
            "avg_rating_without_issue": rating_driver.avg_rating_without_issue,
            "rating_delta": rating_driver.rating_delta,
            "total_mentions": rating_driver.pattern.review_count,
            "peak_meal_period": rating_driver.pattern.peak_meal_period,
            "peak_day": rating_driver.pattern.peak_day,
        },
        "top_marketing_opportunity": None,
        "top_hidden_gem": None,
    }

    if marketing_gap is not None:
        summary["top_marketing_opportunity"] = {
            "product_category": marketing_gap.product_category,
            "customer_mention_count": marketing_gap.customer_mention_count,
            "avg_sentiment_strength": marketing_gap.avg_sentiment_strength,
            "instagram_mention_count": marketing_gap.instagram_mention_count,
            "love_score": marketing_gap.love_score,
            "marketing_score": marketing_gap.marketing_score,
            "gap_score": marketing_gap.gap_score,
        }

    if hidden_gem is not None:
        summary["top_hidden_gem"] = {
            "product_category": hidden_gem.product_category,
            "mention_count": hidden_gem.mention_count,
            "avg_sentiment_strength": hidden_gem.avg_sentiment_strength,
            "sample_positive_points": hidden_gem.sample_positive_points,
        }

    return summary


# ---------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------


class RecommendationService:
    """
    Phase 3 orchestrator: AnalyticsResult -> ExecutiveActionCenter.

    Makes exactly ONE Gemini call per invocation (via
    `GeminiClient.generate_executive_recommendations`), requesting
    narrative copy for all four recommendation slots at once.
    """

    def __init__(self, gemini_client: GeminiClient) -> None:
        self._gemini_client = gemini_client

    def generate(self, analytics: AnalyticsResult) -> ExecutiveActionCenter:
        top_business_impact = _select_top_business_impact(analytics)
        top_rating_driver = _select_top_rating_driver(analytics)
        top_marketing_gap = _select_top_marketing_gap(analytics)
        top_hidden_gem = _select_top_hidden_gem(analytics)

        analytics_summary = _build_analytics_summary(
            business_impact=top_business_impact,
            rating_driver=top_rating_driver,
            marketing_gap=top_marketing_gap,
            hidden_gem=top_hidden_gem,
        )

        try:
            raw_narrative = self._gemini_client.generate_executive_recommendations(
                analytics_summary
            )
        except GeminiClientError as exc:
            raise RecommendationServiceError(
                f"Gemini failed to generate executive recommendations: {exc}"
            ) from exc

        try:
            narrative = _ExecutiveNarrativeBundle.model_validate(raw_narrative)
        except ValidationError as exc:
            raise RecommendationServiceError(
                f"Gemini executive recommendation response failed validation: {exc}"
            ) from exc

        operational_priority = OperationalPriorityRecommendation(
            issue=top_business_impact.issue,
            score=top_business_impact.score,
            headline=narrative.operational_priority.headline,
            impact_analysis=narrative.operational_priority.impact_analysis,
            action_plan=narrative.operational_priority.action_plan,
        )

        rating_driver_rec = RatingDriverRecommendation(
            issue=top_rating_driver.issue,
            rating_delta=top_rating_driver.rating_delta,
            headline=narrative.rating_driver.headline,
            friction_analysis=narrative.rating_driver.friction_analysis,
            mitigation_steps=narrative.rating_driver.mitigation_steps,
        )

        marketing_opportunity: Optional[MarketingOpportunityRecommendation] = None
        if top_marketing_gap is not None and narrative.marketing_opportunity is not None:
            marketing_opportunity = MarketingOpportunityRecommendation(
                product_category=top_marketing_gap.product_category,
                gap_score=top_marketing_gap.gap_score,
                headline=narrative.marketing_opportunity.headline,
                angle_analysis=narrative.marketing_opportunity.angle_analysis,
                campaign_ideas=narrative.marketing_opportunity.campaign_ideas,
            )

        hidden_gem_rec: Optional[HiddenGemRecommendation] = None
        if top_hidden_gem is not None and narrative.hidden_gem is not None:
            hidden_gem_rec = HiddenGemRecommendation(
                product_category=top_hidden_gem.product_category,
                avg_sentiment_strength=top_hidden_gem.avg_sentiment_strength,
                headline=narrative.hidden_gem.headline,
                discovery_analysis=narrative.hidden_gem.discovery_analysis,
                activation_plan=narrative.hidden_gem.activation_plan,
            )

        return ExecutiveActionCenter(
            generated_at=datetime.now(timezone.utc).isoformat(),
            operational_priority=operational_priority,
            rating_driver=rating_driver_rec,
            marketing_opportunity=marketing_opportunity,
            hidden_gem=hidden_gem_rec,
        )