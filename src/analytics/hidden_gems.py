"""
src/analytics/hidden_gems.py

Phase 2 subtask 5 — Hidden Gems.

architecture.md: high positive sentiment, low mention volume. Consumes
the same `ProductPerformance` list `marketing_gap.py` uses (built once
in `customer_love.py`) rather than re-deriving it.

This surfaces low-volume/high-praise drink lines (e.g., a highly rated
but rarely reviewed 'Matcha' or 'Iced Tea' category). If a café has no
qualifying low-volume/high-praise product, it returns an empty list.
"""

from __future__ import annotations

from typing import Dict, List

from src.models.schema import EnrichedReview, HiddenGem, ProductCategory, ProductPerformance, Sentiment

# A menu category needs at least this much positive intensity, on average,
# to count as "clearly loved" rather than just mildly liked.
HIGH_SENTIMENT_MIN = 0.7

# Mention-volume band for "not yet a mainstream favorite"
MIN_MENTIONS = 1
LOW_MENTION_MAX = 3

MAX_SAMPLE_POINTS = 5


def build_hidden_gems(
    reviews: List[EnrichedReview],
    product_performance: List[ProductPerformance],
) -> List[HiddenGem]:
    """
    Candidates: ProductPerformance rows with
    MIN_MENTIONS <= mention_count <= LOW_MENTION_MAX and
    avg_sentiment_strength >= HIGH_SENTIMENT_MIN, sorted by
    avg_sentiment_strength descending.
    """
    positive_points_by_category: Dict[ProductCategory, List[str]] = {}
    for review in reviews:
        if review.product_category and review.sentiment == Sentiment.POSITIVE and review.positive_points:
            positive_points_by_category.setdefault(review.product_category, []).extend(
                review.positive_points
            )

# Change lines 51-53 in src/analytics/hidden_gems.py
    gems: List[HiddenGem] = []
    for perf in product_performance:
        if not (MIN_MENTIONS <= perf.mention_count <= LOW_MENTION_MAX):
            continue
        # Check sentiment_score instead of avg_sentiment_strength
        if perf.sentiment_score < HIGH_SENTIMENT_MIN:
            continue

        gems.append(
            HiddenGem(
                product_category=perf.product_category,
                mention_count=perf.mention_count,
                # Set using sentiment_score
                avg_sentiment_strength=perf.sentiment_score,
                sample_positive_points=positive_points_by_category.get(perf.product_category, [])[
                    :MAX_SAMPLE_POINTS
                ],
            )
        )

    gems.sort(key=lambda g: g.avg_sentiment_strength, reverse=True)
    return gems