# PointPulse AI — Implementation Roadmap

## Project Description

PointPulse AI is an AI-assisted restaurant analytics dashboard that transforms customer reviews into actionable operational and marketing insights.

The system is designed around an **Analytics First, AI Enhanced** architecture.

AI is only responsible for:
- understanding raw customer reviews
- extracting structured information
- rewriting computed analytics into executive recommendations

All analytics, scoring, ranking and trend detection are performed deterministically in Python.

The dashboard answers three executive questions:

1. What operational issue should be fixed first?
2. Which issue is reducing customer ratings the most?
3. What customer-loved strengths are we under-marketing?

---

## Overall Pipeline

```
reviews.csv
instagram.csv
        │
        ▼
Phase 1
Review Enrichment
(Gemini + Python)
        │
        ▼
enriched_reviews.csv
        │
        ▼
Phase 2
Analytics Engine
(Python)
        │
        ▼
AnalyticsResult
        │
        ▼
Phase 3
Executive Recommendation Engine
(Gemini)
        │
        ▼
ExecutiveActionCenter
        │
        ▼
Phase 4
Streamlit Dashboard
```

---

## Technology Stack

### Frontend

- Streamlit
- Plotly

### Backend

- Python 3.11+
- FastAPI

### AI

- Gemini Flash

### Storage

- CSV (MVP)

### Libraries

- pandas
- numpy
- pydantic
- python-dotenv
- google-generativeai

---

# Phase 1 — Review Enrichment Pipeline

### Description

Convert raw customer reviews into structured review data using Gemini.

This phase is responsible only for enrichment.

No analytics or dashboard logic should exist here.

### Input

```
reviews.csv
```

### Output

```
EnrichedReview
```

### Files Created so far 

pointpulse-ai/
├── .env.example
├── README.md
├── requirements.txt
├── data/reviews_seed.csv                     (your real seed data)
└── src/
    ├── main.py                          
    ├── storage/schema.py               
    ├── models/schema.py                
    ├── ai/gemini_client.py              
    ├── services/enrichment_service.py   
    ├── utils/validation.py              
    └── api/enrichment_router.py         
```

### Primary Models

```
RawReview
EnrichedReview
```

### Important Fields

RawReview

```
review
rating
date
time
photos
source
processed
```

Gemini Fields

```
sentiment
sentiment_strength
department
issue
products
brand_attributes
positive_points
has_specific_details
```

Python Computed Fields

```
product_raw
product_category
persisted_meal_period
evidence_weight
processed
```

---

## Subtasks

### 1. Review Models

- RawReview
- EnrichedReview
- enums
    - Sentiment
    - ProductCategory
    - MealPeriod
    - Source

---

### 2. Gemini Client

Implement

```
src/ai/gemini_client.py
```

Responsibilities

- Gemini wrapper
- retries
- JSON parsing
- response validation
- batch requests

---

### 3. Review Enrichment Prompt

Create the production prompt.

Gemini extracts only

- sentiment
- sentiment_strength
- department
- issue
- products
- brand_attributes
- positive_points
- has_specific_details

---

### 4. Enrichment Service

Implement

```
src/services/enrichment_service.py
```

Pipeline

```
Load reviews

↓

filter processed == FALSE

↓

Gemini enrichment

↓

validate

↓

product normalization

↓

meal period

↓

evidence weight

↓

mark processed

↓

save
```

---

### 5. Validation

Implement

```
src/utils/validation.py
```

Validate every Gemini response before saving.

---

### 6. API

Implement

```
POST /api/enrich
```

Returns

```
processed

failed

skipped
```

---

### Phase Deliverable

A fully enriched review dataset.

---

# Phase 2 — Analytics Engine

### Description

Consume enriched review data and Instagram data.

Perform all analytics deterministically in Python.

No AI should be used in this phase.

### Inputs

```
enriched_reviews.csv

instagram.csv
```

### Output

```
AnalyticsResult
```

### Files

```
src/analytics/

engine.py

patterns.py

business_impact.py

rating_driver.py

customer_love.py

hidden_gems.py

marketing_gap.py

api/analytics_router.py
```

### Primary Models

```
AnalyticsResult

IssuePattern

BusinessImpactScore

RatingDriver

CustomerLovedAttribute

HiddenGem

MarketingGap
```

---

## Subtasks

### 1. Issue Analytics

Compute

- issue frequency
- issue trends
- department
- platform
- meal period
- day of week

---

### 2. Business Impact Score

Implement the deterministic formula.

---

### 3. Rating Driver

Find which issue lowers ratings the most.

---

### 4. Customer Love

Compute

- positive attributes
- praised products

---

### 5. Hidden Gems

Compute

- highly loved
- low mention products

---

### 6. Marketing Gap

Read

```
instagram.csv
```

Use simple keyword parsing.

Compare

```
customer loved

vs

marketed products
```

No Gemini.

---

### 7. Analytics Engine

Implement

```
AnalyticsEngine.run()
```

Return

```
AnalyticsResult
```

---

### 8. API

Implement

```
POST /api/analyze
```

---

### Phase Deliverable

A complete deterministic analytics object.

---

# Phase 3 — Executive Recommendation Engine

### Description

Convert computed analytics into executive-level recommendations.

Gemini never receives raw reviews.

It only receives AnalyticsResult.

### Input

```
AnalyticsResult
```

### Output

```
ExecutiveActionCenter
```

### Files

```
src/services/recommendation_service.py

src/api/recommendation_router.py

src/ai/gemini_client.py
```

### Primary Models

```
OperationalPriorityRecommendation

RatingDriverRecommendation

MarketingOpportunityRecommendation

HiddenGemRecommendation

ExecutiveActionCenter
```

---

## Subtasks

### 1. Executive Prompt

Provide

- Business Impact
- Rating Driver
- Marketing Gap
- Hidden Gem

---

### 2. Recommendation Service

Single Gemini request.

Return

```
ExecutiveActionCenter
```

---

### 3. API

Implement

```
POST /api/recommend
```

---

### Phase Deliverable

Complete executive recommendations.

---

# Phase 4 — Dashboard

### Description

Display the analytics.

No calculations should occur inside Streamlit.

The dashboard only consumes API responses.

### Files

```
app.py

dashboard/
```

### Sections

Restaurant Health

Executive Action Center

Business Impact Ranking

Rating Driver

Customer Love

Hidden Gems

Marketing Gap

Platform Distribution

Meal Period

Product Performance

---

## Subtasks

### 1. Dashboard Layout

Create the complete Streamlit layout.

---

### 2. Dashboard Components

Implement every analytics section.

---

### 3. API Integration

Connect

```
POST /api/enrich

POST /api/analyze

POST /api/recommend
```

to the **Get Latest Insights** button.

---

### 4. Placeholder Buttons

Create

```
Sync Reviews
```

Placeholder only.

---

### 5. Loading & Error States

Handle

- empty datasets
- loading
- API failures

---

### Phase Deliverable

A fully functional MVP dashboard capable of demonstrating the complete review → analytics → recommendation pipeline.