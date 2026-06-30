"""Application service that orchestrates screening using LangGraph and hexagonal domain.

This service acts as the bridge between:
- The outer layer (LangGraph for workflow orchestration)
- The inner layer (Hexagonal domain for business logic)

It coordinates the flow while keeping business rules pure in the domain layer.
"""

from typing import Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime, timezone
import uuid

from backend.domain.entities.screening_session import (
    ScreeningSession,
    ScreeningStatus,
    QuestionNode,
)
from backend.domain.value_objects.question import Question, Answer
from backend.domain.value_objects.assessment import AnswerAssessment
from backend.application.ports.question_generator import QuestionGenerator
from backend.domain.services.answer_assessor import AnswerAssessor


# === Configuration ===

@dataclass
class ScreeningConfig:
    """Configuration for screening orchestration."""
    
    # Question counts by tier
    strong_match_questions: int = 2
    partial_match_questions: int = 3
    weak_match_questions: int = 4
    
    # Assessment thresholds
    min_words_for_substantial: int = 20
    strong_answer_threshold: float = 0.8
    vague_answer_threshold: float = 0.5
    
    # Early termination
    allow_early_termination: bool = True
    min_questions_before_skip: int = 1


# === Events ===
# Domain events for external observers

@dataclass
class ScreeningEvent:
    """Base class for screening domain events."""
    session_id: str
    timestamp: datetime
    event_type: str


@dataclass
class QuestionAskedEvent(ScreeningEvent):
    """Emitted when a question is asked."""
    question_id: str
    question_text: str
    question_number: int
    total_questions: int


@dataclass
class AnswerReceivedEvent(ScreeningEvent):
    """Emitted when an answer is received."""
    question_id: str
    answer_text: str
    word_count: int
    response_time_seconds: Optional[float]


@dataclass
class AnswerAssessedEvent(ScreeningEvent):
    """Emitted when an answer is assessed."""
    question_id: str
    quality: str
    decision: str
    confidence: float
    reasoning: str


@dataclass
class ScreeningCompletedEvent(ScreeningEvent):
    """Emitted when screening completes."""
    final_status: str
    questions_asked: int
    sufficient_evidence: bool
    termination_reason: Optional[str]


# === Orchestrator ===

class ScreeningOrchestrator:
    """Application service that orchestrates screening using hexagonal + LangGraph.
    
    This service is the entry point for all screening operations. It:
    1. Coordinates domain entities (ScreeningSession)
    2. Uses LangGraph for workflow orchestration (when available)
    3. Manages ports (QuestionGenerator, AnswerAssessor)
    4. Publishes events for external observers
    
    Architecture:
    ```
    ┌─────────────────────────────────────────────────────────────┐
    │  API / UI Layer (Streamlit, FastAPI)                          │
    │  - Calls: orchestrator.start_screening()                     │
    │  - Calls: orchestrator.receive_answer()                    │
    └───────────────────────┬─────────────────────────────────────┘
                            │
    ┌───────────────────────▼─────────────────────────────────────┐
    │  Application Layer (This Orchestrator)                        │
    │  - Manages domain entities                                     │
    │  - Coordinates with LangGraph (optional)                        │
    │  - Publishes events                                           │
    └───────────────────────┬─────────────────────────────────────┘
                            │
    ┌───────────────────────▼─────────────────────────────────────┐
    │  Domain Layer (Hexagonal)                                     │
    │  - ScreeningSession (aggregate)                                │
    │  - Question, Answer (value objects)                           │
    │  - AnswerAssessor (domain service)                           │
    └───────────────────────┬─────────────────────────────────────┘
                            │
    ┌───────────────────────▼─────────────────────────────────────┐
    │  Infrastructure Layer (Adapters)                              │
    │  - LLMQuestionGenerator (implements QuestionGenerator port) │
    │  - LangGraph workflow (optional orchestration)              │
    └─────────────────────────────────────────────────────────────┘
    ```
    """
    
    def __init__(
        self,
        question_generator: QuestionGenerator,
        answer_assessor: AnswerAssessor,
        config: ScreeningConfig | None = None,
        event_listeners: list[Callable[[ScreeningEvent], None]] | None = None,
    ):
        """Initialize the orchestrator with dependencies.
        
        Args:
            question_generator: Port implementation for question generation
            answer_assessor: Domain service for answer assessment
            config: Configuration options
            event_listeners: Optional callbacks for domain events
        """
        self._question_generator = question_generator
        self._answer_assessor = answer_assessor
        self._config = config or ScreeningConfig()
        self._event_listeners = event_listeners or []
    
    def start_screening(
        self,
        candidate_id: str,
        job_id: str,
        match_tier: str,
    ) -> ScreeningSession:
        """Start a new screening session.
        
        This is the entry point for the screening workflow. It:
        1. Creates a new ScreeningSession aggregate
        2. Generates initial questions using the QuestionGenerator port
        3. Initializes the session with questions
        4. Publishes a QuestionAskedEvent
        
        Args:
            candidate_id: The candidate being screened
            job_id: The job they're being screened for
            match_tier: STRONG_MATCH, PARTIAL_MATCH, or WEAK_MATCH
            
        Returns:
            The initialized ScreeningSession aggregate
        """
        # Determine question count based on tier
        tier_to_count = {
            "STRONG_MATCH": self._config.strong_match_questions,
            "PARTIAL_MATCH": self._config.partial_match_questions,
            "WEAK_MATCH": self._config.weak_match_questions,
        }
        question_count = tier_to_count.get(match_tier, 2)
        
        # Create session aggregate
        session = ScreeningSession(
            candidate_id=candidate_id,
            job_id=job_id,
            match_tier=match_tier,
        )
        
        # Generate questions via port
        questions = self._question_generator.generate_initial_questions(
            candidate_id=candidate_id,
            job_id=job_id,
            match_tier=match_tier,
            count=question_count,
        )
        
        # Initialize session with questions
        session.start_screening(questions)
        
        # Publish event
        current_question = session.current_question
        if current_question:
            self._publish_event(QuestionAskedEvent(
                session_id=session.id,
                timestamp=datetime.now(timezone.utc),
                event_type="question_asked",
                question_id=current_question.id,
                question_text=current_question.text,
                question_number=1,
                total_questions=len(questions),
            ))
        
        return session
    
    def receive_answer(
        self,
        session: ScreeningSession,
        answer_text: str,
    ) -> Answer:
        """Receive and record a candidate's answer.
        
        This method:
        1. Creates an Answer value object
        2. Records it in the ScreeningSession aggregate
        3. Publishes an AnswerReceivedEvent
        4. Triggers assessment (async or sync depending on implementation)
        
        Args:
            session: The active screening session
            answer_text: The candidate's answer text
            
        Returns:
            The recorded Answer value object
        """
        # Create answer value object
        answer = Answer(
            question_id=session.current_question.id if session.current_question else "",
            text=answer_text,
            timestamp=datetime.now(timezone.utc).timestamp(),
        )
        
        # Record in session aggregate
        session.record_answer(answer)
        
        # Get timing info
        current_node = session.question_nodes[session.current_question_index] if session.question_nodes else None
        response_time = None
        if current_node and current_node.asked_at and current_node.answered_at:
            response_time = (current_node.answered_at - current_node.asked_at).total_seconds()
        
        # Publish event
        self._publish_event(AnswerReceivedEvent(
            session_id=session.id,
            timestamp=datetime.now(timezone.utc),
            event_type="answer_received",
            question_id=answer.question_id,
            answer_text=answer.text,
            word_count=answer.word_count(),
            response_time_seconds=response_time,
        ))
        
        return answer
    
    def assess_and_progress(
        self,
        session: ScreeningSession,
    ) -> AnswerAssessment:
        """Assess the current answer and progress the session.
        
        This method:
        1. Calls the AnswerAssessor domain service
        2. Records the assessment in the ScreeningSession
        3. Publishes an AnswerAssessedEvent
        4. Progresses the session based on the assessment decision
        5. Returns the assessment for caller handling
        
        Args:
            session: The active screening session
            
        Returns:
            The AnswerAssessment from the domain service
        """
        # Get current question and answer
        current_idx = session.current_question_index
        if current_idx >= len(session.question_nodes):
            raise ValueError("No current question to assess")
        
        node = session.question_nodes[current_idx]
        question = node.question
        answer = node.answer
        
        if not answer:
            raise ValueError("No answer to assess")
        
        # Assess using domain service
        assessment = self._answer_assessor.assess(
            question=question,
            answer=answer,
            context={
                "tier": session.match_tier,
                "questions_so_far": session.questions_answered,
            },
        )
        
        # Record assessment in session aggregate
        session.record_assessment(assessment)
        
        # Publish event
        self._publish_event(AnswerAssessedEvent(
            session_id=session.id,
            timestamp=datetime.now(timezone.utc),
            event_type="answer_assessed",
            question_id=question.id,
            quality=assessment.quality.value,
            decision=assessment.decision.value,
            confidence=assessment.confidence,
            reasoning=assessment.reasoning,
        ))
        
        # If screening completed, publish completion event
        if session.is_complete:
            self._publish_event(ScreeningCompletedEvent(
                session_id=session.id,
                timestamp=datetime.now(timezone.utc),
                event_type="screening_completed",
                final_status=session.status.value,
                questions_asked=session.questions_answered,
                sufficient_evidence=session.sufficient_evidence,
                termination_reason=session.termination_reason,
            ))
        
        return assessment
    
    def _publish_event(self, event: Any) -> None:
        """Publish an event to all registered listeners."""
        for listener in self._event_listeners:
            try:
                listener(event)
            except Exception as e:
                # Log error but don't break event chain
                # TODO: Add proper logging
                print(f"Event listener error: {e}")
