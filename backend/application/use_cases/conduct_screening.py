"""Application use case for conducting a screening session.

This use case orchestrates the domain logic for screening a candidate.
It coordinates between the domain entities and the infrastructure ports.
"""

from datetime import datetime
from typing import Optional

from backend.domain.entities.screening_session import (
    ScreeningSession,
    ScreeningStatus,
    QuestionNode,
)
from backend.domain.value_objects.question import Question, Answer
from backend.domain.value_objects.assessment import AnswerAssessment
from backend.application.ports.question_generator import QuestionGenerator


class ConductScreeningUseCase:
    """Use case for conducting a candidate screening session."""
    
    def __init__(
        self,
        question_generator: QuestionGenerator,
        # TODO: Add assessment service port
        # TODO: Add repository for persistence
    ):
        self._question_generator = question_generator
    
    def start_screening(
        self,
        candidate_id: str,
        job_id: str,
        match_tier: str,
        question_count: int = 2,
    ) -> ScreeningSession:
        """Start a new screening session.
        
        Args:
            candidate_id: The candidate being screened
            job_id: The job they're being screened for
            match_tier: STRONG_MATCH, PARTIAL_MATCH, or WEAK_MATCH
            question_count: Number of questions to generate (1-4)
            
        Returns:
            A new ScreeningSession in PENDING status
        """
        # Generate questions using the port
        questions = self._question_generator.generate_initial_questions(
            candidate_id=candidate_id,
            job_id=job_id,
            match_tier=match_tier,
            count=question_count,
        )
        
        # Create the session
        session = ScreeningSession(
            candidate_id=candidate_id,
            job_id=job_id,
            match_tier=match_tier,
        )
        
        # Initialize with questions
        session.start_screening(questions)
        
        # TODO: Persist to repository
        
        return session
    
    def ask_current_question(self, session: ScreeningSession) -> Question:
        """Record that the current question has been asked.
        
        Args:
            session: The active screening session
            
        Returns:
            The question being asked
            
        Raises:
            ValueError: If not in a valid state to ask a question
        """
        # Delegate to the domain entity
        question = session.ask_current_question()
        
        # TODO: Persist updated session
        
        return question
    
    def record_answer(
        self,
        session: ScreeningSession,
        answer_text: str,
    ) -> Answer:
        """Record a candidate's answer to the current question.
        
        Args:
            session: The active screening session
            answer_text: The candidate's answer text
            
        Returns:
            The recorded Answer value object
            
        Raises:
            ValueError: If not awaiting an answer
        """
        answer = Answer(
            question_id=session.current_question.id if session.current_question else "",
            text=answer_text,
            timestamp=datetime.utcnow().timestamp(),
        )
        
        session.record_answer(answer)
        
        # TODO: Persist updated session
        
        return answer
    
    def assess_answer(
        self,
        session: ScreeningSession,
        assessment: AnswerAssessment,
    ) -> None:
        """Record assessment of the current answer and advance state.
        
        This is where the core screening logic happens:
        - If answer is strong → may skip to email
        - If vague → may probe or move to next
        - If contradictory → may reject
        
        Args:
            session: The active screening session
            assessment: The assessment of the current answer
        """
        session.record_assessment(assessment)
        
        # TODO: Persist updated session
    
    def get_screening_result(self, session: ScreeningSession) -> dict:
        """Get the final screening result.
        
        Args:
            session: A completed screening session
            
        Returns:
            Dictionary with screening summary, assessments, and recommendation
        """
        if not session.is_complete:
            raise ValueError("Cannot get result for incomplete screening")
        
        return {
            "screening_id": session.id,
            "status": session.status.value,
            "candidate_id": session.candidate_id,
            "job_id": session.job_id,
            "questions_asked": session.questions_answered,
            "assessments": [
                {
                    "question_id": node.question.id,
                    "quality": node.assessment.quality.value if node.assessment else None,
                    "decision": node.assessment.decision.value if node.assessment else None,
                }
                for node in session.question_nodes
                if node.assessment
            ],
            "sufficient_evidence": session.sufficient_evidence,
            "termination_reason": session.termination_reason,
        }
