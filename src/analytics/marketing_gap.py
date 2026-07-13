"""
src/analytics/marketing_gap.py

Phase 2 subtask 6 — Marketing Gap.

Compares what café customers love against what actually gets marketed
on Instagram using deterministic keyword parsing over `InstagramPost.caption`
and `hashtags`.

Answers executive question: "What customer-loved coffee categories are
we under-marketing on social media?"
"""

from __future__ import annotations

from typing import Dict, List

from src.models.schema import InstagramPost, MarketingGap, ProductCategory, ProductPerformance

# Minimum mentions before measuring a marketing gap
MIN_CUSTOMER_MENTIONS = 2

# Sentiment strength floor for a product to count as "loved"
LOVE_SENTIMENT_MIN = 0.6

# Flagged as underrepresented when marketing falls below this threshold
GAP_THRESHOLD = 0.15


def _keyword_for(category: ProductCategory) -> str:
    """Turn a ProductCategory enum value into a plain-English keyword
    for substring matching, e.g. SPECIALTY_COFFEE -> 'specialty coffee'."""
    return category.value.replace("_", " ")


def _post_mentions_category(post: InstagramPost, keyword: str) -> bool:
    haystack = post.caption.casefold()
    if keyword in haystack:
        return True
    for tag in post.hashtags:
        if keyword in tag.replace("_", " ").replace("-", " ").casefold():
            return True
    return False


def build_marketing_gap(
    product_performance: List[ProductPerformance],
    instagram_posts: List[InstagramPost],
) -> List[MarketingGap]:
    """
    One MarketingGap per ProductPerformance entry with at least
    MIN_CUSTOMER_MENTIONS, sorted by gap_score descending.
    """
    if not product_performance:
        return []

    max_customer_mentions = max(p.mention_count for p in product_performance)

    instagram_counts: Dict[ProductCategory, int] = {}
    for perf in product_performance:
        keyword = _keyword_for(perf.product_category)
        instagram_counts[perf.product_category] = sum(
            1 for post in instagram_posts if _post_mentions_category(post, keyword)
        )

    max_instagram_mentions = max(instagram_counts.values(), default=0)

    gaps: List[MarketingGap] = []
    for perf in product_performance:
        if perf.mention_count < MIN_CUSTOMER_MENTIONS:
            continue

        volume_norm = perf.mention_count / max_customer_mentions if max_customer_mentions else 0.0
        love_score = round(0.6 * volume_norm + 0.4 * perf.avg_sentiment_strength, 4)

        ig_count = instagram_counts[perf.product_category]
        marketing_score = round(ig_count / max_instagram_mentions, 4) if max_instagram_mentions else 0.0

        gap_score = round(love_score - marketing_score, 4)

        is_underrepresented = (
            perf.sentiment_score >= LOVE_SENTIMENT_MIN and gap_score >= GAP_THRESHOLD
        )

        gaps.append(
            MarketingGap(
                product_category=perf.product_category,
                customer_mention_count=perf.mention_count,
                avg_sentiment_strength=perf.sentiment_score,
                instagram_mention_count=ig_count,
                love_score=love_score,
                marketing_score=marketing_score,
                gap_score=gap_score,
                is_underrepresented=is_underrepresented,
            )
        )

    gaps.sort(key=lambda g: g.gap_score, reverse=True)
    return gaps