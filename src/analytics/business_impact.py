"""
src/analytics/business_impact.py

Phase 2 subtask 2 — Business Impact Score.

Computes one BusinessImpactScore per issue using the shared
IssuePattern objects and grouped review data prepared by
AnalyticsEngine.

Score =
100 * (
    0.35 * frequency +
    0.30 * negative sentiment +
    0.20 * evidence +
    0.15 * rating penalty
)

The score represents operational impact rather than simply rating
impact. It intentionally differs from RatingDriver, which measures
how strongly an issue lowers café ratings.
"""

from __future__ import annotations

from typing import Dict, List

from src.models.schema import (
    BusinessImpactScore,
    EnrichedReview,
    IssuePattern,
    Sentiment,
)

FREQ_WEIGHT = 0.35
NEG_SENTIMENT_WEIGHT = 0.30
EVIDENCE_WEIGHT_COEF = 0.20
RATING_PENALTY_WEIGHT = 0.15

MAX_EVIDENCE_WEIGHT = 10.0
MAX_RATING_PENALTY = 4.0


def build_business_impact_scores(
    reviews: List[EnrichedReview],
    patterns: List[IssuePattern],
    grouped_reviews: Dict[str, List[EnrichedReview]],
) -> List[BusinessImpactScore]:
    """
    Build one BusinessImpactScore for every issue.

    Parameters
    ----------
    reviews
        Complete enriched café dataset.

    patterns
        Shared IssuePattern objects computed once by AnalyticsEngine.

    grouped_reviews
        Mapping of issue -> reviews for that issue.
    """

    if not grouped_reviews:
        return []

    patterns_by_issue = {p.issue: p for p in patterns}

    overall_avg_rating = (
        sum(r.rating for r in reviews) / len(reviews)
    )

    max_review_count = max(
        len(rows)
        for rows in grouped_reviews.values()
    )

    scores: List[BusinessImpactScore] = []

    for issue, rows in grouped_reviews.items():

        n = len(rows)

        freq_norm = (
            n / max_review_count
            if max_review_count
            else 0.0
        )

        negative_rows = [
            r
            for r in rows
            if r.sentiment == Sentiment.NEGATIVE
        ]

        neg_sentiment_norm = (
            sum(r.sentiment_strength for r in negative_rows)
            / len(negative_rows)
            if negative_rows
            else 0.0
        )

        evidence_norm = min(
            1.0,
            (
                sum(r.evidence_weight for r in rows)
                / n
            )
            / MAX_EVIDENCE_WEIGHT,
        )

        avg_rating = sum(r.rating for r in rows) / n

        rating_penalty_norm = max(
            0.0,
            min(
                1.0,
                (overall_avg_rating - avg_rating)
                / MAX_RATING_PENALTY,
            ),
        )

        score = 100 * (
            FREQ_WEIGHT * freq_norm
            + NEG_SENTIMENT_WEIGHT * neg_sentiment_norm
            + EVIDENCE_WEIGHT_COEF * evidence_norm
            + RATING_PENALTY_WEIGHT * rating_penalty_norm
        )

        scores.append(
            BusinessImpactScore(
                issue=issue,
                score=round(score, 2),
                freq_norm=round(freq_norm, 4),
                neg_sentiment_norm=round(
                    neg_sentiment_norm,
                    4,
                ),
                evidence_norm=round(
                    evidence_norm,
                    4,
                ),
                rating_penalty_norm=round(
                    rating_penalty_norm,
                    4,
                ),
                pattern=patterns_by_issue[issue],
            )
        )

    scores.sort(
        key=lambda score: score.score,
        reverse=True,
    )

    return scores