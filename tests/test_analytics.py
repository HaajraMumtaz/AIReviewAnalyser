import pytest
from datetime import date, time
from src.models.schema import EnrichedReview, InstagramPost, AnalyticsResult, ProductCategory
from src.analytics.engine import AnalyticsEngine

# ==============================================================================
# FIXTURES: Calibrated Datasets to Force Specific Mathematical Outcomes
# ==============================================================================

@pytest.fixture
def calibrated_reviews() -> list[EnrichedReview]:
    """
    A carefully structured dataset designed to test mathematical properties:
    - Overall average rating: (3 + 1 + 5 + 5 + 4) / 5 = 3.6
    - 'slow_valet' (facilities): 1 mention, rating 3 (below avg).
    - 'burnt_food' (kitchen): 1 mention, rating 1 (severe penalty).
    - 'specialty_coffee': 2 positive mentions (highly loved).
    - 'cold_coffee': 1 positive mention (for Hidden Gem evaluation).
    """
    raw_data = [
        # --- ISSUE 1: slow_valet (facilities) ---
        {
            "review_id": "r001",
            "review": "Beautiful place but valet took 25 mins. Total mood killer.",
            "rating": 3,
            "date": date(2026, 6, 22),
            "time": time(18, 30),
            "source": "google",
            "photos": False,
            "processed": True,
            "sentiment": "negative",
            "sentiment_strength": 0.7,
            "department": "facilities",
            "issue": "slow_valet",
            "products": [],
            "brand_attributes": ["beautiful place"],
            "positive_points": ["beautiful place"],
            "has_specific_details": True,
            "evidence_weight": 7.0,
            "persisted_meal_period": "dinner"
        },
        # --- ISSUE 2: burnt_food (kitchen) ---
        {
            "review_id": "r002",
            "review": "Croissant was completely burnt to charcoal! Disgusting.",
            "rating": 1,
            "date": date(2026, 6, 23),
            "time": time(9, 30),
            "source": "google",
            "photos": True,
            "processed": True,
            "sentiment": "negative",
            "sentiment_strength": 1.0,
            "department": "kitchen",
            "issue": "burnt_food",
            "products": ["croissant"],
            "brand_attributes": [],
            "positive_points": [],
            "has_specific_details": True,
            "evidence_weight": 10.0,
            "persisted_meal_period": "breakfast"
        },
        # --- PRODUCT CATEGORY 1: specialty_coffee (highly loved) ---
        {
            "review_id": "r003",
            "review": "Incredible specialty coffee! Super fruity notes.",
            "rating": 5,
            "date": date(2026, 6, 24),
            "time": time(10, 0),
            "source": "google",
            "photos": False,
            "processed": True,
            "sentiment": "positive",
            "sentiment_strength": 0.9,
            "department": "kitchen",
            "issue": None,
            "products": ["pour-over"],
            "product_category": "specialty_coffee",
            "brand_attributes": ["incredible coffee"],
            "positive_points": ["fruity notes"],
            "has_specific_details": True,
            "evidence_weight": 5.0,
            "persisted_meal_period": "breakfast"
        },
        {
            "review_id": "r004",
            "review": "The espresso selection here is unmatched. Flawless.",
            "rating": 5,
            "date": date(2026, 6, 25),
            "time": time(8, 15),
            "source": "google",
            "photos": False,
            "processed": True,
            "sentiment": "positive",
            "sentiment_strength": 0.9,
            "department": "kitchen",
            "issue": None,
            "products": ["espresso"],
            "product_category": "specialty_coffee",
            "brand_attributes": ["flawless coffee"],
            "positive_points": ["unmatched selection"],
            "has_specific_details": True,
            "evidence_weight": 5.0,
            "persisted_meal_period": "breakfast"
        },
        # --- PRODUCT CATEGORY 2: cold_coffee (low volume, high praise -> HIDDEN GEM candidate) ---
        {
            "review_id": "r005",
            "review": "The iced matcha is phenomenal! Underappreciated masterpiece.",
            "rating": 4,
            "date": date(2026, 6, 26),
            "time": time(14, 0),
            "source": "google",
            "photos": True,
            "processed": True,
            "sentiment": "positive",
            "sentiment_strength": 0.8,
            "department": "kitchen",
            "issue": None,
            "products": ["iced matcha"],
            "product_category": "cold_coffee",
            "brand_attributes": ["phenomenal drink"],
            "positive_points": ["phenomenal drink"],
            "has_specific_details": True,
            "evidence_weight": 8.0,
            "persisted_meal_period": "lunch"
        }
    ]
    return [EnrichedReview.model_validate(r) for r in raw_data]

@pytest.fixture
def calibrated_instagram_posts() -> list[InstagramPost]:
    """
    Calibrated to test marketing gaps:
    - Mentions "cold coffee" (represented category).
    - Completely ignores "specialty coffee" (under-marketed category).
    """
    raw_data = [
        {
            "post_id": "ig001",
            "caption": "Beat the heat with our amazing cold coffee options! 🧊☕ #cold_coffee",
            "date": date(2026, 6, 22),
            "campaign": "product_feature"
        }
    ]
    parsed = []
    for p in raw_data:
        p["hashtags"] = ["cold_coffee"]
        parsed.append(InstagramPost.model_validate(p))
    return parsed


# ==============================================================================
# TEST CASES
# ==============================================================================

def test_analytics_engine_end_to_end(calibrated_reviews, calibrated_instagram_posts):
    """Verifies orchestration logic and validates final contract shapes."""
    engine = AnalyticsEngine()
    result = engine.run(reviews=calibrated_reviews, instagram_posts=calibrated_instagram_posts)
    
    assert isinstance(result, AnalyticsResult)
    assert len(result.issue_patterns) == 2
    assert len(result.business_impacts) == 2


def test_business_impact_score_math(calibrated_reviews, calibrated_instagram_posts):
    """
    Validates Business Impact Score calculations:
    Score = 100 * (0.35*freq_norm + 0.30*neg_sent_norm + 0.20*ev_norm + 0.15*penalty_norm)
    """
    engine = AnalyticsEngine()
    result = engine.run(reviews=calibrated_reviews, instagram_posts=calibrated_instagram_posts)
    
    burnt_food_impact = next(bi for bi in result.business_impacts if bi.issue == "burnt_food")
    assert burnt_food_impact.freq_norm == 1.0
    assert burnt_food_impact.neg_sentiment_norm == 1.0
    assert burnt_food_impact.evidence_norm == 1.0
    assert burnt_food_impact.rating_penalty_norm == 0.65
    assert pytest.approx(burnt_food_impact.score, abs=0.01) == 94.75


def test_rating_driver_isolated_deltas(calibrated_reviews, calibrated_instagram_posts):
    """Verifies that Rating Drivers cleanly calculate ratings differences with/without issues."""
    engine = AnalyticsEngine()
    result = engine.run(reviews=calibrated_reviews, instagram_posts=calibrated_instagram_posts)
    
    burnt_food_driver = next(d for d in result.rating_drivers if d.issue == "burnt_food")
    assert burnt_food_driver.avg_rating_with_issue == 1.0
    assert burnt_food_driver.avg_rating_without_issue == 4.25
    assert burnt_food_driver.rating_delta == 3.25


def test_hidden_gems_low_volume_filters(calibrated_reviews, calibrated_instagram_posts):
    """Surfaces categories with low mentions (1 to 3) and high sentiment (>= 0.7)."""
    engine = AnalyticsEngine()
    result = engine.run(reviews=calibrated_reviews, instagram_posts=calibrated_instagram_posts)
    
    assert len(result.hidden_gems) >= 1
    gem_categories = [g.product_category for g in result.hidden_gems]
    assert ProductCategory.COLD_COFFEE in gem_categories
    
    cold_gem = next(g for g in result.hidden_gems if g.product_category == ProductCategory.COLD_COFFEE)
    assert cold_gem.mention_count == 1
    # Check that it validates properly using the field mapped inside your model
    assert hasattr(cold_gem, 'avg_sentiment_strength') or hasattr(cold_gem, 'sentiment_score')


def test_marketing_gap_metric_alignment(calibrated_reviews, calibrated_instagram_posts):
    """Tests the love_score, marketing_score, and gap calculations."""
    engine = AnalyticsEngine()
    result = engine.run(reviews=calibrated_reviews, instagram_posts=calibrated_instagram_posts)
    
    # Changed result.marketing_gaps -> result.marketing_gap
    specialty_gap = next(g for g in result.marketing_gap if g.product_category == ProductCategory.SPECIALTY_COFFEE)
    assert specialty_gap.love_score == 0.96
    assert specialty_gap.marketing_score == 0.0
    assert specialty_gap.gap_score == 0.96
    assert specialty_gap.is_underrepresented is True


def test_graceful_handling_of_empty_inputs():
    """Ensures empty datasets don't cause ZeroDivisionErrors or crashes."""
    engine = AnalyticsEngine()
    
    result = engine.run(reviews=[], instagram_posts=[])
    
    assert result.issue_patterns == []
    assert result.business_impacts == []
    assert result.rating_drivers == []
    assert result.product_performances == []
    assert result.hidden_gems == []
    assert result.marketing_gap == []  # Changed result.marketing_gaps -> result.marketing_gap