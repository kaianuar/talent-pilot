"""Value objects for answer assessment in the screening domain."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AnswerQuality(str, Enum):
    """Quality levels for candidate answers."""
    STRONG = "strong"  # Specific example, clear depth
    ADEQUATE = "adequate"  # Reasonable but not detailed
    VAGUE = "vague"  # Generic, no specifics
    IRRELEVANT = "irrelevant"  # Doesn't answer the question
    CONTRADICTORY = "contradictory"  # Conflicts with previous answers


class AssessmentDecision(str, Enum):
    """Possible decisions after assessing an answer."""
    PROCEED_TO_NEXT_QUESTION = "proceed_to_next"
    PROBE_FOR_CLARITY = "probe_for_clarity"
    SKIP_TO_EMAIL = "skip_to_email"  # Answer was strong enough
    REJECT_CANDIDATE = "reject_candidate"  # Answer shows fundamental mismatch


@dataclass(frozen=True)
class AnswerAssessment:
    """Immutable assessment of a candidate's answer."""
    quality: AnswerQuality
    confidence: float  # 0.0 to 1.0
    key_points_identified: list[str]
    gaps_identified: list[str]
    decision: AssessmentDecision
    reasoning: str  # Why this assessment was made
    
    def is_sufficient_for_tier(self, tier: str) -> bool:
        """Check if answer quality meets tier requirements."""
        tier_thresholds = {
            "STRONG_MATCH": AnswerQuality.ADEQUATE,
            "PARTIAL_MATCH": AnswerQuality.VAGUE,
            "WEAK_MATCH": AnswerQuality.VAGUE,
        }
        required = tier_thresholds.get(tier, AnswerQuality.VAGUE)
        quality_order = [
            AnswerQuality.IRRELEVANT,
            AnswerQuality.CONTRADICTORY,
            AnswerQuality.VAGUE,
            AnswerQuality.ADEQUATE,
            AnswerQuality.STRONG,
        ]
        return quality_order.index(self.quality) >= quality_order.index(required)
