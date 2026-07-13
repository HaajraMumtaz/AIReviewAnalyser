# PointPulse AI — Phase 1: Review Enrichment Pipeline

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# then edit .env and set GEMINI_API_KEY
```

## Run the API

```bash
uvicorn src.main:app --reload
```

- `GET  /health` — liveness check
- `POST /api/enrich` — runs one enrichment pass over `data/reviews.csv`,
  writes/upserts `data/enriched_reviews.csv`, and returns:

  ```json
  {"processed": 28, "failed": [{"review_id": "r001", "error": "..."}], "skipped": 2}
  ```

Interactive docs: http://127.0.0.1:8000/docs

## Data

`data/reviews.csv` ships with 30 sample reviews (`processed=FALSE`) across
Google, Foodpanda, and TripAdvisor. Each `POST /api/enrich` call only
processes rows still marked `FALSE`, so it's safe to call repeatedly —
already-enriched rows are skipped, and rows that failed (Gemini error or
schema-validation error) stay `FALSE` and are retried automatically on
the next call.

## Tests

No formal test suite is included yet (not listed under Phase 1 subtasks).
The pipeline was validated manually end-to-end with a fake `GeminiClient`
against the real seed data — see the implementation summary for what was
checked (idempotent re-runs, isolated per-row failures, retry-on-next-run).
