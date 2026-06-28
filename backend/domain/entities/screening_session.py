"""ScreeningSession aggregate root entity.

This entity manages the entire screening lifecycle for a candidate-job pair.
It enforces invariants, tracks state, and coordinates question/answer flow.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid

from backend.domain.value_objects.question import Question, Answer, QuestionType
from backend.domain.value_objects.assessment import AnswerAssessment, AssessmentDecision


class ScreeningStatus(str, Enum):
    """Status of the screening session."""
    PENDING = "pending"  # Not started yet
    IN_PROGRESS = "in_progress"  # Active screening
    AWAITING_ANSWER = "awaiting_answer"  # Question asked, waiting for response
    ASSESSING = "assessing"  # Answer received, assessing
    COMPLETE = "complete"  # All questions answered
    EARLY_TERMINATION = "early_termination"  # Strong answer allowed skip
    REJECTED = "rejected"  # Candidate rejected during screening


@dataclass
class QuestionNode:
    """Node in the question graph."""
    question: Question
    answer: Optional[Answer] = None
    assessment: Optional[AnswerAssessment] = None
    asked_at: Optional[datetime] = None
    answered_at: Optional[datetime] = None
    
    @property
    def is_answered(self) -> bool:
        return self.answer is not None
    
    @property
    def response_time_seconds(self) -> Optional[float]:
        if self.asked_at and self.answered_at:
            return (self.answered_at - self.asked_at).total_seconds()
        return None


@dataclass
class ScreeningSession:
    """Aggregate root for candidate screening process."""
    
    # Identity
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    candidate_id: str = ""
    job_id: str = ""
    
    # State
    status: ScreeningStatus = ScreeningStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    
    # Question flow
    question_nodes: list[QuestionNode] = field(default_factory=list)
    current_question_index: int = 0
    match_tier: str = "PARTIAL_MATCH"
    
    # Early termination tracking
    sufficient_evidence: bool = False
    termination_reason: Optional[str] = None
    
    # Invariants
    def __post_init__(self):
        """Validate invariants after initialization."""
        if self.status == ScreeningStatus.IN_PROGRESS and not self.question_nodes:
            raise ValueError("Cannot start screening without questions")
    
    @property
    def current_question(self) -> Optional[Question]:
        """Get the current question being asked."""
        if 0 <= self.current_question_index < len(self.question_nodes):
            return self.question_nodes[self.current_question_index].question
        return None
    
    @property
    def questions_answered(self) -> int:
        """Count of answered questions."""
        return sum(1 for node in self.question_nodes if node.is_answered)
    
    @property
    def total_questions(self) -> int:
        """Total questions in the screening."""
        return len(self.question_nodes)
    
    @property
    def is_complete(self) -> bool:
        """Check if screening is complete."""
        return self.status in [ScreeningStatus.COMPLETE, 
                                ScreeningStatus.EARLY_TERMINATION,
                                ScreeningStatus.REJECTED]
    
    def start_screening(self, questions: list[Question]) -> None:
        """Initialize screening with questions."""
        if self.status != ScreeningStatus.PENDING:
            raise ValueError(f"Cannot start screening from status: {self.status}")
        
        self.question_nodes = [QuestionNode(q) for q in questions]
        self.status = ScreeningStatus.IN_PROGRESS
        self.updated_at = datetime.utcnow()
    
    def ask_current_question(self) -> Question:
        """Record that current question has been asked."""
        if self.status not in [ScreeningStatus.IN_PROGRESS, ScreeningStatus.ASSESSING]:
            raise ValueError(f"Cannot ask question in status: {self.status}")
        
        current = self.question_nodes[self.current_question_index]
        current.asked_at = datetime.utcnow()
        self.status = ScreeningStatus.AWAITING_ANSWER
        self.updated_at = datetime.utcnow()
        return current.question
    
    def record_answer(self, answer: Answer) -> None:
        """Record candidate's answer to current question."""
        if self.status != ScreeningStatus.AWAITING_ANSWER:
            raise ValueError(f"Cannot record answer in status: {self.status}")
        
        current = self.question_nodes[self.current_question_index]
        current.answer = answer
        current.answered_at = datetime.utcnow()
        self.status = ScreeningStatus.ASSESSING
        self.updated_at = datetime.utcnow()
    
    def record_assessment(self, assessment: AnswerAssessment) -> None:
        """Record assessment of the current answer."""
        if self.status != ScreeningStatus.ASSESSING:
            raise ValueError(f"Cannot assess in status: {self.status}")
        
        current = self.question_nodes[self.current_question_index]
        current.assessment = assessment
        
        # Handle assessment decision
        if assessment.decision == AssessmentDecision.REJECT_CANDIDATE:
            self.status = ScreeningStatus.REJECTED
            self.termination_reason = assessment.reasoning
            self.completed_at = datetime.utcnow()
        
        elif assessment.decision == AssessmentDecision.SKIP_TO_EMAIL:
            self.sufficient_evidence = True
            self.termination_reason = f"Early termination: {assessment.reasoning}"
            self.status = ScreeningStatus.EARLY_TERMINATION
            self.completed_at = datetime.utcnow()
        
        elif assessment.decision == AssessmentDecision.PROBE_FOR_CLARITY:
            # Stay on same question, will generate probe
            self.status = ScreeningStatus.IN_PROGRESS
        
        else:  # PROCEED_TO_NEXT_QUESTION
            self.current_question_index += 1
            if self.current_question_index >= len(self.question_nodes):
                self.status = ScreeningStatus.COMPLETE
                self.completed_at = datetime.utcnow()
            else:
                self.status = ScreeningStatus.IN_PROGRESS
        
        self.updated_at = datetime.utcnow()
    
    def to_dict(self) -> dict:
        """Serialize screening session to dict."""
        return {
            "id": self.id,
            "candidate_id": self.candidate_id,
            "job_id": self.job_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "questions": [
                {
                    "question": {
                        "id": node.question.id,
                        "text": node.question.text,
                        "type": node.question.type.value,
                        "priority": node.question.priority.value,
                        "focus_area": node.question.focus_area,
                    },
                    "answer": {
                        "text": node.answer.text,
                        "timestamp": node.answer.timestamp,
                    } if node.answer else None,
                    "assessment": {
                        "quality": node.assessment.quality.value,
                        "confidence": node.assessment.confidence,
                        "decision": node.assessment.decision.value,
                        "reasoning": node.assessment.reasoning,
                    } if node.assessment else None,
                    "asked_at": node.asked_at.isoformat() if node.asked_at else None,
                    "answered_at": node.answered_at.isoformat() if node.answered_at else None,
                }
                for node in self.question_nodes
            ],
            "current_question_index": self.current_question_index,
            "match_tier": self.match_tier,
            "sufficient_evidence": self.sufficient_evidence,
            "termination_reason": self.termination_reason,
        }
