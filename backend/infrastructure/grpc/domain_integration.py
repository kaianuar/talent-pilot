"""Integration layer between gRPC servicer and hexagonal domain.

This module provides the glue code that connects the gRPC servicer to
the hexagonal domain layer, ensuring proper dependency injection and
separation of concerns.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, Callable, AsyncIterator
from dataclasses import dataclass
from datetime import datetime

from backend.domain.entities.screening_session import (
    ScreeningSession,
    ScreeningStatus,
    QuestionNode,
)
from backend.domain.value_objects.question import Question, QuestionType
from backend.domain.value_objects.assessment import (
    AnswerAssessment,
    AssessmentDecision,
    AnswerQuality,
)
from backend.domain.services.answer_assessor import AnswerAssessor
from backend.application.services.screening_orchestrator import (
    ScreeningOrchestrator,
    ScreeningConfig,
)
from backend.application.ports.question_generator import QuestionGenerator

# Infrastructure adapters
from backend.infrastructure.adapters.llm_question_generator import (
    LLMQuestionGenerator,
)
from backend.infrastructure.adapters.llm_answer_assessor import LLMAnswerAssessor

# gRPC imports
from backend.infrastructure.grpc.proto import screening_pb2


logger = logging.getLogger(__name__)


@dataclass
class DomainDependencies:
    """Container for domain dependencies.
    
    This class holds all the dependencies needed by the domain layer,
    making it easy to inject them where needed.
    """
    question_generator: QuestionGenerator
    answer_assessor: AnswerAssessor
    config: ScreeningConfig
    
    @classmethod
    def create_default(cls) -> "DomainDependencies":
        """Create default dependencies."""
        return cls(
            question_generator=LLMQuestionGenerator(),
            answer_assessor=LLMAnswerAssessor(),
            config=ScreeningConfig(),
        )


class ScreeningDomainService:
    """Domain service for screening operations.
    
    This service acts as the bridge between the gRPC layer and the domain layer,
    handling all the business logic and coordinating domain operations.
    """
    
    def __init__(
        self,
        dependencies: Optional[DomainDependencies] = None,
    ):
        """Initialize the domain service.
        
        Args:
            dependencies: Domain dependencies (uses defaults if not provided)
        """
        self._deps = dependencies or DomainDependencies.create_default()
        self._sessions: Dict[str, ScreeningSession] = {}
        self._progress_callbacks: Dict[str, list] = {}
        
        logger.info("ScreeningDomainService initialized")
    
    def _create_orchestrator(self) -> ScreeningOrchestrator:
        """Create a new screening orchestrator with dependencies."""
        return ScreeningOrchestrator(
            question_generator=self._deps.question_generator,
            answer_assessor=self._deps.answer_assessor,
            config=self._deps.config,
        )
    
    def _to_proto_question(self, question: Question) -> screening_pb2.Question:
        """Convert domain Question to protobuf Question."""
        return screening_pb2.Question(
            id=question.id,
            text=question.text,
            type=question.type.value,
            focus_area=question.focus_area,
            expected_evidence=question.expected_evidence,
            priority=question.priority.value,
        )
    
    def _to_proto_assessment(
        self,
        assessment: AnswerAssessment,
    ) -> screening_pb2.Assessment:
        """Convert domain AnswerAssessment to protobuf Assessment."""
        return screening_pb2.Assessment(
            quality=assessment.quality.value,
            confidence=assessment.confidence,
            key_points_identified=assessment.key_points_identified,
            gaps_identified=assessment.gaps_identified,
            decision=assessment.decision.value,
            reasoning=assessment.reasoning,
        )
    
    def _to_proto_email_draft(
        self,
        draft: Dict[str, str],
    ) -> screening_pb2.EmailDraft:
        """Convert email draft dict to protobuf EmailDraft."""
        return screening_pb2.EmailDraft(
            to=draft.get("to", ""),
            subject=draft.get("subject", ""),
            body=draft.get("body", ""),
            cc=draft.get("cc", ""),
            bcc=draft.get("bcc", ""),
        )
    
    async def start_screening(
        self,
        candidate_id: str,
        job_id: str,
        match_tier: str,
        question_count: Optional[int] = None,
    ) -> Dict[str, any]:
        """Start a new screening session.
        
        Args:
            candidate_id: The candidate ID
            job_id: The job ID
            match_tier: The match tier (STRONG_MATCH, PARTIAL_MATCH, WEAK_MATCH)
            question_count: Optional number of questions
            
        Returns:
            Dictionary with screening_id, first_question, and success status
        """
        try:
            logger.info(f"Starting screening for candidate {candidate_id}, job {job_id}")
            
            # Create orchestrator
            orchestrator = self._create_orchestrator()
            
            # Override config if question count provided
            if question_count:
                orchestrator._config = orchestrator._config.__class__(
                    strong_match_questions=question_count,
                    partial_match_questions=question_count,
                    weak_match_questions=question_count,
                )
            
            # Start screening
            session = orchestrator.start_screening(
                candidate_id=candidate_id,
                job_id=job_id,
                match_tier=match_tier,
            )
            
            # Store session
            self._sessions[session.id] = session
            
            # Get first question
            first_question = None
            if session.question_nodes:
                first_node = session.question_nodes[0]
                if first_node.question:
                    first_question = self._to_proto_question(first_node.question)
            
            logger.info(f"Screening {session.id} started successfully")
            
            return {
                "screening_id": session.id,
                "success": True,
                "first_question": first_question,
            }
            
        except Exception as e:
            logger.exception("Start screening failed")
            return {
                "success": False,
                "error_message": str(e),
            }
    
    async def submit_answer(
        self,
        screening_id: str,
        candidate_id: str,
        question_id: str,
        answer_text: str,
        response_time_seconds: Optional[float] = None,
    ) -> Dict[str, any]:
        """Submit an answer and get the next question or final result.
        
        Args:
            screening_id: The screening session ID
            candidate_id: The candidate ID
            question_id: The question ID being answered
            answer_text: The answer text
            response_time_seconds: Optional response time
            
        Returns:
            Dictionary with assessment, next_question, is_complete, email_draft
        """
        try:
            logger.info(f"Submitting answer for screening {screening_id}")
            
            # Get session
            session = self._sessions.get(screening_id)
            if not session:
                return {
                    "success": False,
                    "error_message": "Screening session not found",
                }
            
            # Create orchestrator
            orchestrator = self._create_orchestrator()
            orchestrator._session = session
            
            # Submit answer
            result = orchestrator.submit_answer(
                question_id=question_id,
                answer_text=answer_text,
                response_time_seconds=response_time_seconds,
            )
            
            # Get assessment
            assessment = None
            if result.get('assessment'):
                assessment = self._to_proto_assessment(result['assessment'])
            
            # Check if complete
            is_complete = result.get('is_complete', False)
            
            # Get next question if not complete
            next_question = None
            if not is_complete and result.get('next_question'):
                next_question = self._to_proto_question(result['next_question'])
            
            # Get email draft if complete
            email_draft = None
            if is_complete and result.get('email_draft'):
                email_draft = self._to_proto_email_draft(result['email_draft'])
            
            logger.info(f"Answer submitted for screening {screening_id}, is_complete={is_complete}")
            
            return {
                "assessment": assessment,
                "next_question": next_question,
                "is_complete": is_complete,
                "email_draft": email_draft,
            }
            
        except Exception as e:
            logger.exception("Submit answer failed")
            return {
                "success": False,
                "error_message": str(e),
            }


# Create domain service instance
domain_service = ScreeningDomainService()
