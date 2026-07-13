"""
src/analytics/engine.py

Phase 2 — Analytics Engine.

Single orchestration layer for deterministic coffee analytics pipeline.
"""

from __future__ import annotations

from typing import List

from src.analytics.business_impact import build_business_impact_scores
from src.analytics.customer_love import build_customer_love
from src.analytics.hidden_gems import build_hidden_gems
from src.analytics.marketing_gap import build_marketing_gap
from src.analytics.patterns import (
    build_issue_patterns,
    group_by_issue,
)
from src.analytics.rating_driver import build_rating_drivers
from src.models.schema import (
    AnalyticsResult,
    EnrichedReview,
    InstagramPost,
)


class AnalyticsEngine:
    """
    Runs the complete deterministic analytics pipeline.

        Enriched Coffee Reviews
                │
                ▼
        group_by_issue()
                │
                ▼
        build_issue_patterns()
                │
                ├────────► Business Impact
                │
                ├────────► Rating Drivers
                │
                └────────► Customer Love
                              │
                              ├────────► Hidden Gems
                              │
                              └────────► Marketing Gap
                                           ▲
                                           │
                                    Instagram Posts
    """

    def run(
        self,
        reviews: List[EnrichedReview],
        instagram_posts: List[InstagramPost],
    ) -> AnalyticsResult:

        # ----------------------------------------------------------
        # Shared intermediate objects
        # ----------------------------------------------------------

        grouped_reviews = group_by_issue(reviews)

        issue_patterns = build_issue_patterns(
            grouped_reviews
        )

        customer_love = build_customer_love(
            reviews
        )

        # ----------------------------------------------------------
        # Issue analytics
        # ----------------------------------------------------------

        business_impact = build_business_impact_scores(
            reviews=reviews,
            patterns=issue_patterns,
            grouped_reviews=grouped_reviews,
        )

        rating_drivers = build_rating_drivers(
            reviews=reviews,
            patterns=issue_patterns,
            grouped_reviews=grouped_reviews,
        )

        # ----------------------------------------------------------
        # Product analytics
        # ----------------------------------------------------------

        hidden_gems = build_hidden_gems(
            reviews=reviews,
            product_performance=customer_love.products,
        )

        marketing_gap = build_marketing_gap(
            customer_love.products,
            instagram_posts,
        )

        # ----------------------------------------------------------
        # Final result
        # ----------------------------------------------------------

        return AnalyticsResult(
            issue_patterns=issue_patterns,
            business_impacts=business_impact,
            rating_drivers=rating_drivers,
            customer_love=customer_love.attributes,
            product_performances=customer_love.products,
            hidden_gems=hidden_gems,
            marketing_gap=marketing_gap,
        )