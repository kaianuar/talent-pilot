"""LangGraph screening workflow that orchestrates hexagonal domain.

This module creates a LangGraph workflow that:
1. Wraps the domain entities (ScreeningSession aggregate)
2. Coordinates nodes for question generation, answer recording, assessment
3. Handles conditional routing (probe, proceed, skip, reject)
4. Maintains clean separation between orchestration (LangGraph) and business logic (Domain)
"""

from typing import Literal, Callable
from datetime import datetime

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from backend.infrastructure.orchestration.langgraph_schema import (
    ScreeningGraphState,
    create_initial_state,
    get_screening_summary,
)
from backend.domain.entities.screening_session import (
    ScreeningSession,
    ScreeningStatus,
    QuestionNode,
)
from backend.domain.value_objects.question import Question, Answer
from backend.domain.value_objects.assessment import (
    AnswerAssessment,
    AnswerQuality,
    AssessmentDecision,
)
from backend.application.ports.question_generator import QuestionGenerator
from backend.domain.services.answer_assessor import AnswerAssessor


# === Node Functions ===
# Each node receives the state, does work, and returns state updates
# Nodes delegate to domain entities for business logic

def generate_question_node(state: ScreeningGraphState) -> ScreeningGraphState:
    """Node: Generate the next question using LLM.
    
    This node:
    1. Checks if we need a new question or a follow-up probe
    2. Calls the QuestionGenerator port (implemented by LLM adapter)
    3. Adds the question to the ScreeningSession aggregate
    """
    session = state["screening_session"]
    
    # Check if we need a probe question (previous answer was vague)
    current_node_idx = session.current_question_index
    if current_node_idx < len(session.question_nodes):
        current_node = session.question_nodes[current_node_idx]
        if current_node.assessment and current_node.assessment.decision == AssessmentDecision.PROBE_FOR_CLARITY:
            # Generate probe question
            # TODO: Get QuestionGenerator from context/dependency injection
            # For now, mark that we need a probe
            return {
                **state,
                "current_node": "generate_probe",
                "generated_question_text": None,  # Will be filled by probe generator
            }
    
    # Normal question generation
    # The question should already be in the session from start_screening
    # This node is more about presenting it to the user
    current_question = session.current_question
    
    return {
        **state,
        "current_node": "awaiting_answer",
        "generated_question_text": current_question.text if current_question else None,
        "last_updated": datetime.utcnow(),
    }


def await_answer_node(state: ScreeningGraphState, user_input: str) -> ScreeningGraphState:
    """Node: Receive and record the candidate's answer.
    
    This node:
    1. Takes the user's answer from input
    2. Creates an Answer value object
    3. Records it in the ScreeningSession aggregate
    """
    session = state["screening_session"]
    
    # Create answer value object
    answer = Answer(
        question_id=session.current_question.id if session.current_question else "",
        text=user_input,
        timestamp=datetime.utcnow().timestamp(),
    )
    
    # Record in domain entity
    session.record_answer(answer)
    
    return {
        **state,
        "user_input": user_input,
        "current_node": "assessing",
        "last_updated": datetime.utcnow(),
    }


def assess_answer_node(state: ScreeningGraphState) -> ScreeningGraphState:
    """Node: Assess the candidate's answer.
    
    This node:
    1. Calls the AnswerAssessor domain service
    2. Records the assessment in the ScreeningSession
    3. Determines next step (probe, proceed, skip, reject)
    """
    session = state["screening_session"]
    
    # Get current question and answer
    current_idx = session.current_question_index
    if current_idx >= len(session.question_nodes):
        # Should not happen, but handle gracefully
        return {
            **state,
            "current_node": END,
        }
    
    node = session.question_nodes[current_idx]
    question = node.question
    answer = node.answer
    
    if not answer:
        # Should not happen
        return {
            **state,
            "current_node": END,
        }
    
    # Assess the answer using domain service
    # TODO: Get assessor from dependency injection
    # For now, create with default LLM client
    assessor = AnswerAssessor()  # Will use heuristics only without LLM
    
    assessment = assessor.assess(
        question=question,
        answer=answer,
        context={
            "tier": session.match_tier,
            "questions_so_far": session.questions_answered,
        },
    )
    
    # Record assessment in session
    session.record_assessment(assessment)
    
    return {
        **state,
        "assessment": assessment,
        "current_node": "routing",  # Will be resolved by conditional edge
        "last_updated": datetime.utcnow(),
    }


def route_after_assessment(state: ScreeningGraphState) -> Literal["ask_question", "probe", "draft_email", "end"]:
    """Conditional edge: Determine next step after assessment.
    
    This function inspects the assessment and decides where to route next.
    """
    session = state["screening_session"]
    
    # Check if screening is complete
    if session.is_complete:
        return "end"
    
    # Check assessment decision
    current_idx = session.current_question_index
    if current_idx < len(session.question_nodes):
        node = session.question_nodes[current_idx]
        if node.assessment:
            decision = node.assessment.decision
            
            if decision == AssessmentDecision.SKIP_TO_EMAIL:
                return "draft_email"
            elif decision == AssessmentDecision.PROBE_FOR_CLARITY:
                return "probe"
            elif decision == AssessmentDecision.REJECT_CANDIDATE:
                return "end"
            else:  # PROCEED_TO_NEXT_QUESTION
                return "ask_question"
    
    # Default: continue asking questions
    return "ask_question"


def draft_email_node(state: ScreeningGraphState) -> ScreeningGraphState:
    """Node: Draft email to recruiter (terminal node)."""
    # This would call the email drafting service
    # For now, just mark as complete
    session = state["screening_session"]
    session.status = ScreeningStatus.COMPLETE
    
    return {
        **state,
        "current_node": END,
    }


# === Graph Assembly ===

def create_screening_graph(
    question_generator: QuestionGenerator,
    answer_assessor: AnswerAssessor,
) -> StateGraph:
    """Create and configure the screening workflow graph.
    
    Args:
        question_generator: The port implementation for question generation
        answer_assessor: The domain service for answer assessment
        
    Returns:
        Configured StateGraph ready for compilation
    """
    
    # Create the graph with our state schema
    workflow = StateGraph(ScreeningGraphState)
    
    # Add nodes
    workflow.add_node("generate_question", generate_question_node)
    workflow.add_node("awaiting_answer", lambda state: state)  # Pass-through node
    workflow.add_node("assessing", assess_answer_node)
    workflow.add_node("draft_email", draft_email_node)
    
    # Add conditional routing after assessment
    workflow.add_conditional_edges(
        "assessing",
        route_after_assessment,
        {
            "ask_question": "generate_question",
            "probe": "generate_question",  # Would generate probe question
            "draft_email": "draft_email",
            "end": END,
        },
    )
    
    # Set entry point
    workflow.set_entry_point("generate_question")
    
    return workflow


def compile_screening_graph(
    question_generator: QuestionGenerator,
    answer_assessor: AnswerAssessor,
    checkpointer=None,
) -> any:
    """Compile the screening graph for execution.
    
    Args:
        question_generator: The port implementation for question generation
        answer_assessor: The domain service for answer assessment
        checkpointer: Optional checkpointer for persistence
        
    Returns:
        Compiled graph ready for invocation
    """
    workflow = create_screening_graph(question_generator, answer_assessor)
    
    if checkpointer:
        return workflow.compile(checkpointer=checkpointer)
    
    return workflow.compile()
