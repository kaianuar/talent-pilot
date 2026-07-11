"""gRPC servicer implementation for the ScreeningService.

This module implements the gRPC ScreeningService defined in screening.proto,
integrating with the hexagonal domain layer for business logic.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, AsyncIterator
import asyncio

import grpc
from google.protobuf.timestamp_pb2 import Timestamp

# Import generated protobuf code
from backend.infrastructure.grpc.proto import screening_pb2
from backend.infrastructure.grpc.proto import screening_pb2_grpc

# Domain imports
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

# Infrastructure imports
from backend.infrastructure.adapters.llm_question_generator import (
    LLMQuestionGenerator,
)
from backend.infrastructure.adapters.llm_answer_assessor import LLMAnswerAssessor


logger = logging.getLogger(__name__)


class ScreeningServicer(screening_pb2_grpc.ScreeningServiceServicer):
    """gRPC servicer implementing the ScreeningService.
    
    This servicer integrates with the hexagonal domain layer,
    delegating all business logic to domain services and entities.
    """
    
    def __init__(self):
        """Initialize the servicer with domain dependencies."""
        super().__init__()
        
        # Initialize infrastructure adapters
        self._question_generator = LLMQuestionGenerator()
        self._answer_assessor = LLMAnswerAssessor()
        
        # In-memory session store (replace with persistent storage in production)
        self._sessions: Dict[str, ScreeningSession] = {}
        self._progress_observers: Dict[str, list] = {}
        
        logger.info("ScreeningServicer initialized")
    
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
    
    def _to_proto_assessment(self, assessment: AnswerAssessment) -> screening_pb2.Assessment:
        """Convert domain AnswerAssessment to protobuf Assessment."""
        return screening_pb2.Assessment(
            quality=assessment.quality.value,
            confidence=assessment.confidence,
            key_points_identified=assessment.key_points_identified,
            gaps_identified=assessment.gaps_identified,
            decision=assessment.decision.value,
            reasoning=assessment.reasoning,
        )
    
    def _to_proto_answer_assessment(self, assessment: AnswerAssessment, question_id: str = "") -> screening_pb2.AnswerAssessment:
        """Convert domain AnswerAssessment to protobuf AnswerAssessment (for SubmitAnswer)."""
        return screening_pb2.AnswerAssessment(
            question_id=question_id,
            quality=assessment.quality.value,
            confidence=assessment.confidence,
            key_points_identified=assessment.key_points_identified,
            gaps_identified=assessment.gaps_identified,
            decision=assessment.decision.value,
            reasoning=assessment.reasoning,
        )
    
    def _to_proto_email_draft(self, draft: Dict[str, str]) -> screening_pb2.EmailDraft:
        """Convert email draft dict to protobuf EmailDraft."""
        return screening_pb2.EmailDraft(
            to=draft.get("to", ""),
            subject=draft.get("subject", ""),
            body=draft.get("body", ""),
            cc=draft.get("cc", ""),
            bcc=draft.get("bcc", ""),
        )
    
    def _create_progress_update(
        self,
        session: ScreeningSession,
        status: str,
    ) -> screening_pb2.ScreeningProgressUpdate:
        """Create a progress update from session state."""
        current_question = session.current_question_index
        total = len(session.question_nodes)
        progress = (current_question / max(total, 1)) * 100 if total > 0 else 0
        
        # Get current question text if available
        current_question_text = ""
        if current_question < total:
            current_node = session.question_nodes[current_question]
            if current_node.question:
                current_question_text = current_node.question.text
        
        return screening_pb2.ScreeningProgressUpdate(
            screening_id=session.id,
            status=status,
            current_question_number=current_question + 1,  # 1-indexed for UI
            total_questions=total,
            progress_percentage=progress,
            current_question_text=current_question_text,
            timestamp=datetime.now(timezone.utc).isoformat() + "Z",
        )
    
    def StartScreening(
        self,
        request: screening_pb2.StartScreeningRequest,
        context: grpc.ServicerContext,
    ) -> screening_pb2.StartScreeningResponse:
        """Start a new screening session."""
        try:
            logger.info(f"StartScreening called for candidate {request.candidate_id}, job {request.job_id}")
            
            # Create orchestrator with config
            config = ScreeningConfig(
                strong_match_questions=request.question_count if request.question_count else 2,
                partial_match_questions=request.question_count if request.question_count else 3,
                weak_match_questions=request.question_count if request.question_count else 4,
            )
            
            orchestrator = ScreeningOrchestrator(
                question_generator=self._question_generator,
                answer_assessor=self._answer_assessor,
                config=config,
            )
            
            # Start screening session
            session = orchestrator.start_screening(
                candidate_id=request.candidate_id,
                job_id=request.job_id,
                match_tier=request.match_tier,
            )
            
            # Store session
            self._sessions[session.id] = session
            
            # Get first question - need to ask it first to transition state
            first_question_text = session.ask_current_question()
            first_question = None
            if session.question_nodes:
                first_node = session.question_nodes[0]
                if first_node.question:
                    first_question = self._to_proto_question(first_node.question)
            
            logger.info(f"Screening {session.id} started successfully")
            
            return screening_pb2.StartScreeningResponse(
                screening_id=session.id,
                success=True,
                first_question=first_question,
            )
            
        except Exception as e:
            logger.exception("StartScreening failed")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return screening_pb2.StartScreeningResponse(
                success=False,
                error_message=str(e),
            )
    
    def GetNextQuestion(
        self,
        request: screening_pb2.GetNextQuestionRequest,
        context: grpc.ServicerContext,
    ) -> screening_pb2.GetNextQuestionResponse:
        """Get the next question for the screening session."""
        try:
            session = self._sessions.get(request.screening_id)
            if not session:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Screening session not found")
                return screening_pb2.GetNextQuestionResponse()
            
            current_idx = session.current_question_index
            total = len(session.question_nodes)
            
            if current_idx >= total:
                # Screening is complete
                return screening_pb2.GetNextQuestionResponse(
                    has_more_questions=False,
                    is_complete=True,
                )
            
            # Get current question
            current_node = session.question_nodes[current_idx]
            if current_node.question:
                question = self._to_proto_question(current_node.question)
                
                # Get preliminary assessment if available
                preliminary = None
                if current_node.answer and current_node.assessment:
                    preliminary = self._to_proto_assessment(current_node.assessment)
                
                return screening_pb2.GetNextQuestionResponse(
                    question=question,
                    has_more_questions=True,
                    is_complete=False,
                    preliminary_assessment=preliminary,
                )
            
            return screening_pb2.GetNextQuestionResponse(
                has_more_questions=False,
                is_complete=True,
            )
            
        except Exception as e:
            logger.exception("GetNextQuestion failed")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return screening_pb2.GetNextQuestionResponse()
    
    def SubmitAnswer(
        self,
        request: screening_pb2.SubmitAnswerRequest,
        context: grpc.ServicerContext,
    ) -> screening_pb2.SubmitAnswerResponse:
        """Submit an answer and get the next question or final result."""
        try:
            logger.info(f"SubmitAnswer called for screening {request.screening_id}")
            
            session = self._sessions.get(request.screening_id)
            if not session:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Screening session not found")
                return screening_pb2.SubmitAnswerResponse()
            
            # Create orchestrator
            config = ScreeningConfig()
            orchestrator = ScreeningOrchestrator(
                question_generator=self._question_generator,
                answer_assessor=self._answer_assessor,
                config=config,
            )
            orchestrator._session = session
            
            # Get current question
            current_idx = session.current_question_index
            if current_idx >= len(session.question_nodes):
                # Session is complete
                result = orchestrator.get_screening_result()
                email_draft = self._to_proto_email_draft(result.get('email_draft', {}))
                
                return screening_pb2.SubmitAnswerResponse(
                    is_complete=True,
                    email_draft=email_draft,
                )
            
            current_node = session.question_nodes[current_idx]
            if not current_node.question:
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details("No current question found")
                return screening_pb2.SubmitAnswerResponse()
            
            # Submit answer to the session
            answer = orchestrator.receive_answer(
                session=session,
                answer_text=request.answer_text,
            )
            
            # Assess and progress the session
            assessment = orchestrator.assess_and_progress(session=session)
            
            # Convert assessment to proto (AnswerAssessment type for SubmitAnswer)
            question_id = current_node.question.id if current_node.question else ""
            proto_assessment = self._to_proto_answer_assessment(assessment, question_id) if assessment else None
            
            # Check if complete (all terminal states)
            is_complete = session.is_complete
            
            # Get next question if not complete
            next_question = None
            if not is_complete and session.current_question:
                # Check if we need to probe (same question, different wording)
                if assessment.decision == AssessmentDecision.PROBE_FOR_CLARITY:
                    # Generate a follow-up probe question
                    probe = self._question_generator.generate_follow_up_probe(
                        original_question=session.current_question,
                        vague_answer=answer.text,
                        context={"tier": session.match_tier},
                    )
                    # Replace current question node with the probe
                    session.question_nodes[session.current_question_index].question = probe
                    session.ask_current_question()
                    next_question = self._to_proto_question(probe)
                else:
                    # Move to next question
                    session.ask_current_question()
                    next_question = self._to_proto_question(session.current_question)
            
            # Get email draft if complete
            email_draft = None
            if is_complete:
                # Build email draft from session data
                email_draft = screening_pb2.EmailDraft(
                    to=f"recruiter@example.com",
                    subject=f"Screening Result for {session.candidate_id}",
                    body=f"Screening completed for {session.candidate_id}. Status: {session.status.value}",
                )
            
            logger.info(f"SubmitAnswer completed for screening {request.screening_id}, is_complete={is_complete}")
            
            return screening_pb2.SubmitAnswerResponse(
                assessment=proto_assessment,
                next_question=next_question,
                is_complete=is_complete,
                email_draft=email_draft,
            )
            
        except Exception as e:
            logger.exception("SubmitAnswer failed")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return screening_pb2.SubmitAnswerResponse()
    
    def GetScreeningResult(
        self,
        request: screening_pb2.GetScreeningResultRequest,
        context: grpc.ServicerContext,
    ) -> screening_pb2.GetScreeningResultResponse:
        """Get the final screening result and email draft."""
        try:
            session = self._sessions.get(request.screening_id)
            if not session:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Screening session not found")
                return screening_pb2.GetScreeningResultResponse(
                    success=False,
                    error_message="Screening session not found",
                )
            
            # Build summary
            summary = screening_pb2.ScreeningSummary(
                screening_id=session.id,
                candidate_id=session.candidate_id,
                job_id=session.job_id,
                status=session.status.value,
                total_questions_asked=session.questions_answered,
                final_assessment=session.termination_reason or "In Progress",
                sufficient_evidence=session.sufficient_evidence,
                termination_reason=session.termination_reason or "",
                created_at=session.created_at.isoformat() if session.created_at else "",
                completed_at=session.completed_at.isoformat() if session.completed_at else "",
            )
            
            # Build QA history
            qa_history = []
            for node in session.question_nodes:
                if node.question and node.answer:
                    qa = screening_pb2.QuestionAnswer(
                        question=self._to_proto_question(node.question),
                        answer_text=node.answer.text,
                        assessment=self._to_proto_answer_assessment(node.assessment, node.question.id) if node.assessment else None,
                        response_time_seconds=str(node.answer.timestamp) if node.answer.timestamp else "0",
                        timestamp=str(node.answer.timestamp) if node.answer.timestamp else "",
                    )
                    qa_history.append(qa)
            
            return screening_pb2.GetScreeningResultResponse(
                success=True,
                summary=summary,
                qa_history=qa_history,
            )
            
        except Exception as e:
            logger.exception("GetScreeningResult failed")
            return screening_pb2.GetScreeningResultResponse(
                success=False,
                error_message=str(e),
            )
    
    def StreamScreeningProgress(
        self,
        request: screening_pb2.StreamScreeningProgressRequest,
        context: grpc.ServicerContext,
    ):
        """Stream real-time screening progress updates.
        
        Note: This is a synchronous method that yields values.
        The actual async handling is done by gRPC's streaming mechanism.
        """
        try:
            session = self._sessions.get(request.screening_id)
            if not session:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Screening session not found")
                return
            
            # Create a simple synchronous generator for progress updates
            # In a real implementation, this would coordinate with the session
            # For now, yield a single initial update
            initial_update = self._create_progress_update(session, "CONNECTED")
            yield initial_update
            
            # Note: Full streaming implementation would require:
            # - A way to get updates from the session
            # - A mechanism to handle multiple concurrent streams
            # - Proper synchronization between threads
            
            # For production, consider using an async gRPC servicer
            # or a separate pub/sub mechanism for streaming updates
                        
        except Exception as e:
            logger.exception("StreamScreeningProgress failed")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
    
    def _notify_progress_observers(
        self,
        screening_id: str,
        status: str,
    ):
        """Notify all observers of a progress update."""
        if screening_id not in self._progress_observers:
            return
        
        session = self._sessions.get(screening_id)
        if not session:
            return
        
        update = self._create_progress_update(session, status)
        
        # Queue update for all observers
        for observer_queue in self._progress_observers[screening_id]:
            try:
                observer_queue.put_nowait(update)
            except asyncio.QueueFull:
                pass  # Observer is slow, skip this update
