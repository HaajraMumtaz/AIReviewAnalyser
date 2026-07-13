"""
src/analytics/rating_driver.py

Phase 2 subtask 3 — Rating Driver Analysis.

For each issue: average rating of reviews carrying that issue vs.
average rating of every other review. Helps isolate what operational problems
are causing the biggest drops in customer satisfaction at the espresso bar.
"""

from __future__ import annotations

from typing import Dict, List

from src.models.schema import EnrichedReview, IssuePattern, RatingDriver


def build_rating_drivers(
    reviews: List[EnrichedReview],
    patterns: List[IssuePattern],
    grouped_reviews: Dict[str, List[EnrichedReview]],
) -> List[RatingDriver]:
    """One RatingDriver per issue, sorted by rating_delta descending."""
    if not grouped_reviews:
        return []

    patterns_by_issue = {p.issue: p for p in patterns}

    drivers: List[RatingDriver] = []
    for issue, rows in grouped_reviews.items():
        with_ratings = [r.rating for r in rows]
        without_ratings = [r.rating for r in reviews if r.issue != issue]

        avg_with = sum(with_ratings) / len(with_ratings)
        avg_without = sum(without_ratings) / len(without_ratings) if without_ratings else avg_with
        
        # Calculate rating delta (negative impact of the issue)
        rating_delta = round(avg_without - avg_with, 2)

        drivers.append(
            RatingDriver(
                issue=issue,
                avg_rating_with_issue=round(avg_with, 2),
                avg_rating_without_issue=round(avg_without, 2),
                rating_delta=rating_delta,  # <--- Added to satisfy the schema!
                pattern=patterns_by_issue[issue],
            )
        )

    # Sort by rating_delta descending so the worst drivers bubble to the top
    drivers.sort(key=lambda d: d.rating_delta, reverse=True)
    return drivers