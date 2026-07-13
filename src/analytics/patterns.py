"""
src/analytics/patterns.py

Phase 2 subtask 1 — Issue Analytics.

Builds one IssuePattern per distinct issue label present in the
enriched reviews: frequency, peak day/bar-period, weekend share,
affected coffee lines, and platform/day breakdowns.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, List

from src.models.schema import EnrichedReview, IssuePattern


def group_by_issue(reviews: List[EnrichedReview]) -> Dict[str, List[EnrichedReview]]:
    """Reviews with no issue (None) are excluded."""
    grouped: Dict[str, List[EnrichedReview]] = defaultdict(list)
    for review in reviews:
        if review.issue:
            grouped[review.issue].append(review)
    return grouped


def build_issue_patterns(
    grouped_reviews: Dict[str, List[EnrichedReview]]
) -> List[IssuePattern]:
    """One IssuePattern per issue, sorted by review_count descending."""
    patterns: List[IssuePattern] = []
    for issue, rows in grouped_reviews.items():
        n = len(rows)
        day_counts = Counter(r.day_of_week for r in rows)
        meal_counts = Counter(r.persisted_meal_period for r in rows if r.persisted_meal_period)
        platform_counts = Counter(r.source for r in rows)
        department_counts = Counter(r.department for r in rows if r.department)
        weekend_count = sum(1 for r in rows if r.day_of_week.is_weekend)
        products_affected = sorted(
            {r.product_category for r in rows if r.product_category},
            key=lambda category: category.value,
        )

        patterns.append(
            IssuePattern(
                issue=issue,
                review_count=n,
                peak_day=day_counts.most_common(1)[0][0] if day_counts else None,
                peak_meal_period=meal_counts.most_common(1)[0][0] if meal_counts else None,
                weekend_share=round(weekend_count / n, 4) if n else 0.0,
                products_affected=products_affected,
                department=department_counts.most_common(1)[0][0] if department_counts else None,
                platform_breakdown=dict(platform_counts),
                day_of_week_breakdown=dict(day_counts),
                meal_period_breakdown=dict(meal_counts),
            )
        )

    patterns.sort(key=lambda p: p.review_count, reverse=True)
    return patterns