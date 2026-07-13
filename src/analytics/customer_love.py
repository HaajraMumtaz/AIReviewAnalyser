"""
src/analytics/customer_love.py

Phase 2 subtask 4 — Customer Love.

Two related-but-distinct aggregates, both built here since they share
a grouping pass over the same reviews and both feed downstream Phase 2
modules:

    build_customer_loved_attributes()
        Freeform praise text (`brand_attributes` + `positive_points`)
        grouped by normalized attribute string. Backs the dashboard's
        "Customer Love" panel and the Marketing Gap's attribute half.

    build_product_performance()
        Praised-and-criticized performance per canonical coffee/beverage
        `product_category`. Backs the dashboard's "Product Performance"
        section, and is the shared input `hidden_gems.py` and
        `marketing_gap.py` both consume.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, NamedTuple

from src.models.schema import CustomerLovedAttribute, EnrichedReview, ProductCategory, ProductPerformance, Sentiment


class CustomerLove(NamedTuple):
    """Bundles the two aggregates this module produces so callers that
    need both (AnalyticsEngine, hidden_gems.py, marketing_gap.py) can
    get them from a single grouping pass over `reviews`."""

    attributes: List[CustomerLovedAttribute]
    products: List[ProductPerformance]


def build_customer_love(reviews: List[EnrichedReview]) -> CustomerLove:
    """Entry point used by AnalyticsEngine. Runs both aggregates and
    returns them together so downstream modules never have to guess
    whether the two are in sync — they come from the same reviews list
    in the same call."""
    return CustomerLove(
        attributes=build_customer_loved_attributes(reviews),
        products=build_product_performance(reviews),
    )


def build_customer_loved_attributes(reviews: List[EnrichedReview]) -> List[CustomerLovedAttribute]:
    """
    One CustomerLovedAttribute per distinct praise phrase (case-folded
    for grouping so "Excellent barista" and "excellent barista" don't
    fragment into two entries), sorted by mention_count then
    avg_sentiment_strength descending.
    """
    strengths: Dict[str, List[float]] = defaultdict(list)
    display_text: Dict[str, str] = {}

    for review in reviews:
        mentioned_this_review = set()
        for raw in (*review.brand_attributes, *review.positive_points):
            text = raw.strip()
            if not text:
                continue
            key = text.casefold()
            display_text.setdefault(key, text)
            mentioned_this_review.add(key)

        for key in mentioned_this_review:
            strengths[key].append(review.sentiment_strength)

    attributes = [
        CustomerLovedAttribute(
            attribute=display_text[key],
            mention_count=len(values),
            avg_sentiment_strength=round(sum(values) / len(values), 4),
        )
        for key, values in strengths.items()
    ]
    attributes.sort(key=lambda a: (a.mention_count, a.avg_sentiment_strength), reverse=True)
    return attributes


def build_product_performance(reviews: List[EnrichedReview]) -> List[ProductPerformance]:
    """
    One ProductPerformance per canonical beverage/add-on `product_category`
    present in the data (reviews with no category are excluded). Sorted by
    mention_count descending.
    """
    rows_by_category: Dict[ProductCategory, List[EnrichedReview]] = defaultdict(list)
    for review in reviews:
        if review.product_category:
            rows_by_category[review.product_category].append(review)

    performances: List[ProductPerformance] = []
    for category, rows in rows_by_category.items():
        n = len(rows)
        
        # Calculate signed sentiment score (Positive is +, Negative is -)
        total_signed_sentiment = sum(
            r.sentiment_strength if r.sentiment == Sentiment.POSITIVE
            else -r.sentiment_strength if r.sentiment == Sentiment.NEGATIVE
            else 0.0
            for r in rows
        )
        sentiment_score = round(total_signed_sentiment / n, 4)

        performances.append(
            ProductPerformance(
                product_category=category,
                mention_count=n,
                avg_sentiment_strength=round(sum(r.sentiment_strength for r in rows) / n, 4),
                sentiment_score=sentiment_score,  # <--- Added this line to satisfy schema
                avg_rating=round(sum(r.rating for r in rows) / n, 2),
                positive_mentions=sum(1 for r in rows if r.sentiment == Sentiment.POSITIVE),
                negative_mentions=sum(1 for r in rows if r.sentiment == Sentiment.NEGATIVE),
            )
        )

    performances.sort(key=lambda p: p.mention_count, reverse=True)
    return performances