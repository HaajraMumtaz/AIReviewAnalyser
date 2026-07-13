"""
src/models/schema.py

Domain models for PointPulse AI.
This schema serves as the single source of truth for all domain models.
"""

from __future__ import annotations

from datetime import date as Date
from datetime import time as Time
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from src.storage.schema import InstagramSchema as IGS
from src.storage.schema import ReviewsSchema as RS

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Sentiment(str, Enum):
    """Sentiment classification for reviews."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class Source(str, Enum):
    """Origin sources for reviews and customer feedback."""

    GOOGLE = "google"
    FOODPANDA = "foodpanda"
    TRIPADVISOR = "tripadvisor"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    OTHER = "other"


class Department(str, Enum):
    """Organizational departments responsible for service aspects."""

    COFFEE = "coffee"
    SERVICE = "service"
    MANAGEMENT = "management"
    CLEANLINESS = "cleanliness"
    AMBIANCE = "ambiance"
    PRICING = "pricing"
    FACILITIES = "facilities"
    DELIVERY = "delivery"
    EVENTS = "events"
    KITCHEN="kitchen"
    FRONT_OF_HOUSE = "front of house"
    OTHER = "other"


class MealPeriod(str, Enum):
    """Meal periods derived from timestamps."""

    BREAKFAST = "breakfast"
    BRUNCH = "brunch"
    LUNCH = "lunch"
    DINNER = "dinner"
    LATE_NIGHT = "late_night"

    @classmethod
    def from_time(cls, t: Optional[Time]) -> Optional["MealPeriod"]:
        """Maps a given time to a specific meal period."""
        if t is None:
            return None
        h = t.hour
        if 5 <= h < 11:
            return cls.BREAKFAST
        elif 11 <= h < 12:
            return cls.BRUNCH
        elif 12 <= h < 16:
            return cls.LUNCH
        elif 16 <= h < 22:
            return cls.DINNER
        else:
            return cls.LATE_NIGHT


class DayOfWeek(str, Enum):
    """Standard days of the week."""

    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"

    @property
    def is_weekend(self) -> bool:
        """Indicates if the day is a weekend day."""
        return self in (DayOfWeek.SATURDAY, DayOfWeek.SUNDAY)

    @classmethod
    def from_date(cls, d: Date) -> "DayOfWeek":
        """Determines the day of the week from a date object."""
        mapping = {
            0: cls.MONDAY,
            1: cls.TUESDAY,
            2: cls.WEDNESDAY,
            3: cls.THURSDAY,
            4: cls.FRIDAY,
            5: cls.SATURDAY,
            6: cls.SUNDAY,
        }
        return mapping[d.weekday()]


class Campaign(str, Enum):
    """Instagram and marketing campaign categories."""

    DISCOUNT = "discount"
    EVENT = "event"
    VIBE = "vibe"
    PRODUCT_FEATURE = "product_feature"
    EDUCATIONAL = "educational"
    TEAM_SPOTLIGHT = "team_spotlight"


class ProductCategory(str, Enum):
    """Specialty coffee product categories."""

    SPECIALTY_COFFEE = "specialty_coffee"
    HOT_COFFEE = "hot_coffee"
    COLD_COFFEE = "cold_coffee"
    POUR_OVER = "pour_over"
    MATCHA = "matcha"
    ICED_TEA = "iced_tea"
    FRAPPE = "frappe"
    SMOOTHIE = "smoothie"
    HOT_CHOCOLATE = "hot_chocolate"
    TEA = "tea"
    ADD_ON = "add_on"
    OTHER = "other"


# ---------------------------------------------------------------------------
# Review Models
# ---------------------------------------------------------------------------


class RawReview(BaseModel):
    """Represents a raw customer review before enrichment."""

    model_config = ConfigDict(populate_by_name=True)

    review_id: str = Field(alias=RS.REVIEW_ID)
    review: str = Field(alias=RS.REVIEW)
    rating: int = Field(alias=RS.RATING, ge=1, le=5)
    date: Date = Field(alias=RS.DATE)
    time: Optional[Time] = Field(default=None, alias=RS.TIME)
    photos: bool = Field(default=False, alias=RS.PHOTOS)
    source: Source = Field(alias=RS.SOURCE)
    processed: bool = Field(default=False, alias=RS.PROCESSED)

    @field_validator("time", mode="before")
    @classmethod
    def _blank_time_to_none(cls, v):
        return None if v in ("", None) else v

    @computed_field
    @property
    def word_count(self) -> int:
        """Computes the word count of the review text."""
        return len(self.review.split())

    @computed_field
    @property
    def day_of_week(self) -> DayOfWeek:
        """Determines the day of the week for the review."""
        return DayOfWeek.from_date(self.date)

    @computed_field
    @property
    def meal_period(self) -> Optional[MealPeriod]:
        """Derives the meal period from the review time."""
        return MealPeriod.from_time(self.time)


class GeminiExtractedFields(BaseModel):
    """Intermediate model containing fields parsed by AI analysis."""

    sentiment: Sentiment
    sentiment_strength: float = Field(ge=0.0, le=1.0)
    department: Department
    issue: Optional[str] = None
    products: List[str] = Field(default_factory=list)
    product_raw: Optional[str] = None
    product_category: Optional[ProductCategory] = None
    brand_attributes: List[str] = Field(default_factory=list)
    positive_points: List[str] = Field(default_factory=list)
    has_specific_details: bool = False

    @field_validator("issue", mode="before")
    @classmethod
    def _blank_issue_to_none(cls, v):
        return None if v in ("", None) else v


class EnrichedReview(RawReview):
    """An enriched customer review containing analytical and AI dimensions."""

    sentiment: Sentiment = Field(alias=RS.SENTIMENT)
    sentiment_strength: float = Field(alias=RS.SENTIMENT_STRENGTH, ge=0.0, le=1.0)
    department: Department = Field(alias=RS.DEPARTMENT)
    issue: Optional[str] = Field(default=None, alias=RS.ISSUE)
    products: List[str] = Field(default_factory=list, alias=RS.PRODUCTS)
    product_raw: Optional[str] = Field(default=None, alias=RS.PRODUCT_RAW)
    product_category: Optional[ProductCategory] = Field(
        default=None, alias=RS.PRODUCT_CATEGORY
    )
    brand_attributes: List[str] = Field(default_factory=list, alias=RS.BRAND_ATTRIBUTES)
    positive_points: List[str] = Field(default_factory=list, alias=RS.POSITIVE_POINTS)
    has_specific_details: bool = Field(default=False, alias=RS.HAS_SPECIFIC_DETAILS)
    persisted_meal_period: Optional[MealPeriod] = Field(
        default=None, alias=RS.MEAL_PERIOD
    )
    evidence_weight: float = Field(alias=RS.EVIDENCE_WEIGHT, ge=0.0, le=10.0)
    processed: bool = Field(default=True, alias=RS.PROCESSED)

    @staticmethod
    def compute_evidence_weight(
        *,
        word_count: int,
        has_photos: bool,
        has_specific_details: bool,
        has_products: bool,
        has_positive_points: bool,
        has_issue: bool,
    ) -> float:
        """Determines the mathematical weight of evidence for a review."""
        if word_count <= 3:
            length_score = 0.3
        elif word_count <= 10:
            length_score = 1.0
        elif word_count <= 25:
            length_score = 2.0
        else:
            length_score = 3.0

        score = 0.8 + length_score
        score += 3.0 if has_photos else 0.0
        score += 3.5 if has_specific_details else 0.0
        score += 1.0 if has_products else 0.0
        score += 0.7 if (has_positive_points and has_issue) else 0.0

        return max(0.0, min(10.0, round(score, 2)))


# ---------------------------------------------------------------------------
# Instagram Models
# ---------------------------------------------------------------------------


class InstagramCaption(BaseModel):
    """Represents raw Instagram caption metadata."""

    model_config = ConfigDict(populate_by_name=True)

    caption_id: str = Field(alias=IGS.CAPTION_ID)
    caption: str = Field(alias=IGS.CAPTION)
    date: Date = Field(alias=IGS.DATE)
    campaign: Optional[Campaign] = Field(default=None, alias=IGS.CAMPAIGN)


class InstagramPost(BaseModel):
    """Represents a fully structured Instagram post."""

    model_config = ConfigDict(populate_by_name=True)

    post_id: str = Field(alias=IGS.CAPTION_ID)
    caption: str = Field(alias=IGS.CAPTION)
    date: Date = Field(alias=IGS.DATE)
    campaign: Optional[Campaign] = Field(default=None, alias=IGS.CAMPAIGN)
    hashtags: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Analytics Models
# ---------------------------------------------------------------------------


class IssuePattern(BaseModel):
    """Aggregate trend metrics and distributions for a single service issue."""

    issue: str
    review_count: int
    peak_day: Optional[DayOfWeek] = None
    peak_meal_period: Optional[MealPeriod] = None
    weekend_share: float = Field(ge=0.0, le=1.0)
    products_affected: List[ProductCategory] = Field(default_factory=list)
    department: Optional[Department] = None
    platform_breakdown: Dict[Source, int] = Field(default_factory=dict)


class BusinessImpactScore(BaseModel):
    """Contains the composite Business Impact Score and its components."""

    issue: str
    score: float = Field(ge=0.0, le=100.0)
    freq_norm: float = Field(ge=0.0, le=1.0)
    neg_sentiment_norm: float = Field(ge=0.0, le=1.0)
    evidence_norm: float = Field(ge=0.0, le=1.0)
    rating_penalty_norm: float = Field(ge=0.0, le=1.0)
    pattern: IssuePattern


class RatingDriver(BaseModel):
    """Quantifies the customer rating impact of a given issue."""

    issue: str
    avg_rating_with_issue: float = Field(ge=1.0, le=5.0)
    avg_rating_without_issue: float = Field(ge=1.0, le=5.0)
    rating_delta: float
    pattern: IssuePattern


class CustomerLovedAttribute(BaseModel):
    """Presents a positive customer feedback point."""

    attribute: str
    mention_count: int
    avg_sentiment_strength: float = Field(ge=0.0, le=1.0)


class ProductPerformance(BaseModel):
    """Aggregated performance metrics for a specific coffee category."""

    product_category: ProductCategory
    mention_count: int
    avg_rating: float = Field(ge=1.0, le=5.0)
    sentiment_score: float
    sentiment_score: float = 0.0


class HiddenGem(BaseModel):
    """High-praise, low-volume product category discovery."""

    product_category: ProductCategory
    mention_count: int
    avg_sentiment_strength: float = Field(ge=0.0, le=1.0)
    sample_positive_points: List[str] = Field(default_factory=list)


class MarketingGap(BaseModel):
    """Highlights differences between customer love and campaign focus."""

    top_loved_attributes: List[CustomerLovedAttribute] = Field(default_factory=list)
    campaign_breakdown: Dict[Campaign, int] = Field(default_factory=dict)
    under_marketed: List[str] = Field(default_factory=list)


class AnalyticsResult(BaseModel):
    """Container grouping all computed analytical deliverables."""

    issue_patterns: List[IssuePattern] = Field(default_factory=list)
    business_impacts: List[BusinessImpactScore] = Field(default_factory=list)
    rating_drivers: List[RatingDriver] = Field(default_factory=list)
    loved_attributes: List[CustomerLovedAttribute] = Field(default_factory=list)
    product_performances: List[ProductPerformance] = Field(default_factory=list)
    hidden_gems: List[HiddenGem] = Field(default_factory=list)
    marketing_gap: List[MarketingGap] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Executive Action Center
# ---------------------------------------------------------------------------


class Recommendation(BaseModel):
    """Base model for executive recommendation cards."""

    narrative: Optional[str] = None


class OperationalPriorityRecommendation(Recommendation):
    """Recommendation cards driven by Business Impact Scores."""

    impact: BusinessImpactScore


class RatingDriverRecommendation(Recommendation):
    """Recommendation cards identifying critical rating drivers."""

    driver: RatingDriver


class MarketingOpportunityRecommendation(Recommendation):
    """Recommendation cards showcasing marketing opportunities or gaps."""

    gap: MarketingGap


class HiddenGemRecommendation(Recommendation):
    """Recommendation cards featuring a high-potential hidden gem."""

    gem: HiddenGem


class ExecutiveActionCenter(BaseModel):
    """The central payload consolidating all prioritized recommendation outputs."""

    operational_priority: OperationalPriorityRecommendation
    rating_driver: RatingDriverRecommendation
    marketing_opportunity: MarketingOpportunityRecommendation
    hidden_gem: Optional[HiddenGemRecommendation] = None