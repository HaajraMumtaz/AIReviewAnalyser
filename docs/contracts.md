# PointPulse AI Context

## Project

Restaurant analytics dashboard

Pipeline

reviews.csv
→ Gemini Enrichment
→ enriched_reviews.csv
→ Analytics Engine
→ Executive Recommendations
→ Dashboard

---

## Directory

src/
    ai/
        gemini_client.py
    analytics/
        patterns.py
        business_impact.py
        rating_driver.py
        customer_love.py
        hidden_gems.py
        marketing_gap.py
        engine.py
    api/
        enrichment_router.py
        analytics_router.py
    services/
        enrichment_service.py
    utils/
        validation.py
    models/
        schema.py
    storage/
        schema.py

---

# Phase 1

## enrichment_service.py

Purpose

RawReview
→ Gemini
→ Validation
→ Product Normalization
→ Meal Period
→ Evidence Weight
→ Save EnrichedReview

Dependencies

GeminiClient
validate_gemini_response
RawReview
EnrichedReview

Public API

normalize_products()

EnrichmentService
    run()
    _build_enriched_review()

---

## validation.py

Purpose

Validate Gemini JSON before persistence.

Dependencies

GeminiExtractedFields

Public API

validate_gemini_response()

---

# Phase 2

Execution Order

AnalyticsEngine.run()

↓

build_issue_patterns()

↓

build_business_impact_scores()

↓

build_rating_drivers()

↓

build_customer_love()

↓

build_hidden_gems()

↓

build_marketing_gap()

↓

AnalyticsResult

---

## patterns.py

Purpose

Build reusable IssuePattern objects.

Dependencies

EnrichedReview
IssuePattern

Public API

group_by_issue()
build_issue_patterns()

Returns

List[IssuePattern]
Dict[str, List[EnrichedReview]]

---

## business_impact.py

Purpose

Business impact scoring using shared IssuePatterns.

Dependencies

EnrichedReview
IssuePattern
BusinessImpactScore

Public API

build_business_impact_scores()

Input

reviews
patterns

Returns

List[BusinessImpactScore]

---

## rating_driver.py

Purpose

Determine which issue lowers ratings the most.

Dependencies

EnrichedReview
IssuePattern
RatingDriver

Public API

build_rating_drivers()

Input

reviews
patterns

Returns

List[RatingDriver]

---

## customer_love.py

Purpose

Compute customer-loved attributes and product performance.

Dependencies

EnrichedReview
CustomerLovedAttribute
ProductPerformance

Public API

build_customer_love()

Internally

build_customer_loved_attributes()
build_product_performance()

Returns

CustomerLove

---

## hidden_gems.py

Purpose

Find highly-loved but low-mentioned products.

Dependencies

ProductPerformance

Public API

build_hidden_gems()

Input

product_performance

Returns

List[HiddenGem]

---

## marketing_gap.py

Purpose

Compare Instagram marketing against customer demand.

Dependencies

InstagramPost
ProductPerformance

Public API

build_marketing_gap()

Input

instagram_posts
product_performance

Returns

List[MarketingGap]

---

## engine.py

Purpose

Single orchestration layer.

Dependencies

patterns
business_impact
rating_driver
customer_love
hidden_gems
marketing_gap

Public API

AnalyticsEngine.run()

Returns

AnalyticsResult

---

## Models

RawReview

EnrichedReview

GeminiExtractedFields

IssuePattern

BusinessImpactScore

RatingDriver

CustomerLove

CustomerLovedAttribute

ProductPerformance

HiddenGem

MarketingGap

AnalyticsResult

ExecutiveActionCenter

---

## Rules

- Gemini is only used during enrichment and recommendation generation.
- Analytics are 100% deterministic Python.
- IssuePattern is computed once by AnalyticsEngine and reused downstream.
- ProductPerformance is computed once and reused by Hidden Gems and Marketing Gap.
- Extend existing architecture. Do not redesign modules or duplicate logic.


## Design Principles

- Keep modules single-responsibility.
- Never duplicate analytics already computed elsewhere.
- Prefer passing computed objects rather than recomputing them.
- Reuse existing Pydantic models.
- Keep analytics deterministic.
- Keep Gemini isolated behind GeminiClient.
- Preserve existing project architecture.