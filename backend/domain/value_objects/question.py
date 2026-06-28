"""Value objects for screening questions."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class QuestionType(str, Enum):
    """Types of screening questions."""
    TECHNICAL_DEPTH = "technical_depth"  # "Explain how X works under the hood"
    EXPERIENCE_VERIFICATION = "experience_verification"  # "Tell me about a time when..."
    PROBLEM_SOLVING = "problem_solving"  # "How would you approach..."
    CULTURE_FIT = "culture_fit"  # "How do you prefer to work..."
    GAP_PROBE = "gap_probe"  # "I notice you don't have X experience..."


class QuestionPriority(str, Enum):
    """Priority levels for questions."""
    REQUIRED = "required"  # Must be answered satisfactorily
    IMPORTANT = "important"  # Should be answered
    BONUS = "bonus"  # Nice to have


@dataclass(frozen=True)
class Question:
    """Immutable screening question value object."""
    id: str  # Unique identifier
    text: str  # The actual question text
    type: QuestionType
    priority: QuestionPriority
    focus_area: str  # e.g., "React hooks", "System design", "Team collaboration"
    expected_evidence: list[str]  # What a good answer should contain
    follow_up_trigger: Optional[str] = None  # Condition to trigger follow-up
    
    def get_assessment_criteria(self) -> str:
        """Get human-readable assessment criteria for this question."""
        criteria = f"**{self.focus_area}**\n"
        criteria += "Strong answer should include:\n"
        for evidence in self.expected_evidence:
            criteria += f"  • {evidence}\n"
        return criteria


@dataclass(frozen=True)
class Answer:
    """Immutable candidate answer value object."""
    question_id: str
    text: str  # The actual answer text
    timestamp: float  # When answer was received
    
    def word_count(self) -> int:
        """Get word count of answer."""
        return len(self.text.split())
    
    def contains_keywords(self, keywords: list[str]) -> list[str]:
        """Check which keywords appear in answer."""
        found = []
        lower_text = self.text.lower()
        for kw in keywords:
            if kw.lower() in lower_text:
                found.append(kw)
        return found
