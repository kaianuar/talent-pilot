"""LangGraph state schema that bridges to hexagonal domain entities.

This module defines the state structure used by LangGraph while maintaining
clean separation from the domain layer.
"""

from dataclasses import dataclass, field
from typing import Annotated, Optional, Literal, TypedDict
from datetime import datetime, timezone
import operator

from backend.domain.entities.screening_session import ScreeningSession
from backend.domain.value_objects.assessment import AnswerAssessment


# === State Field Reducers ===
# These tell LangGraph how to merge state updates

def merge_dicts(old: dict, new: dict) -> dict:
    """Deep merge two dictionaries."""
    result = old.copy()
    for key, value in new.items():
        if isinstance(value, dict) and key in result and isinstance(result[key], dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


def replace(old, new):
    """Always replace with new value."""
    return new


def append_to_list(old: list, new: list) -> list:
    """Append new items to list."""
    return old + new


# === TypedDict State Schema ===
# This is what LangGraph uses internally

class ScreeningGraphState(TypedDict):
    """LangGraph state for screening workflow.
    
    This state bridges between LangGraph's execution model and
    the hexagonal domain architecture.
    """
    
    # === Domain Entity (Central State) ===
    # The aggregate root - all other state derives from this
    screening_session: Annotated[ScreeningSession, replace]
    
    # === Node Tracking ===
    # Which node is currently executing
    current_node: Annotated[str, replace]
    
    # History of nodes visited (for debugging/auditing)
    node_history: Annotated[list[str], append_to_list]
    
    # === User Input Buffer ===
    # Input from the user (candidate's answer)
    user_input: Annotated[Optional[str], replace]
    
    # === LLM Outputs ===
    # Generated question from LLM
    generated_question_text: Annotated[Optional[str], replace]
    
    # Assessment from LLM
    assessment: Annotated[Optional[AnswerAssessment], replace]
    
    # === Error Handling ===
    # If an error occurred, store it here
    error: Annotated[Optional[dict], replace]
    
    # === Metadata ===
    # When the screening started
    started_at: Annotated[datetime, replace]
    
    # When the last update occurred
    last_updated: Annotated[datetime, replace]


# === State Factory ===

def create_initial_state(
    screening_session: ScreeningSession,
) -> ScreeningGraphState:
    """Create initial state for a new screening workflow.
    
    Args:
        screening_session: The initialized screening session aggregate
        
    Returns:
        Initial graph state ready for LangGraph execution
    """
    now = datetime.now(timezone.utc)
    
    return {
        "screening_session": screening_session,
        "current_node": "start",
        "node_history": [],
        "user_input": None,
        "generated_question_text": None,
        "assessment": None,
        "error": None,
        "started_at": now,
        "last_updated": now,
    }


# === State Selectors ===
# Helper functions to extract commonly used state

def get_current_question(state: ScreeningGraphState) -> Optional[dict]:
    """Get the current question from the session."""
    session = state["screening_session"]
    current = session.current_question
    if current:
        return {
            "id": current.id,
            "text": current.text,
            "type": current.type.value,
            "focus_area": current.focus_area,
            "expected_evidence": current.expected_evidence,
        }
    return None


def get_current_answer(state: ScreeningGraphState) -> Optional[dict]:
    """Get the most recent answer from the session."""
    session = state["screening_session"]
    if session.question_nodes and session.current_question_index < len(session.question_nodes):
        node = session.question_nodes[session.current_question_index]
        if node.answer:
            return {
                "text": node.answer.text,
                "word_count": node.answer.word_count(),
                "timestamp": node.answer.timestamp,
            }
    return None


def is_screening_complete(state: ScreeningGraphState) -> bool:
    """Check if the screening session is complete."""
    return state["screening_session"].is_complete


def get_screening_summary(state: ScreeningGraphState) -> dict:
    """Get a summary of the screening progress."""
    session = state["screening_session"]
    
    return {
        "session_id": session.id,
        "status": session.status.value,
        "progress": f"{session.questions_answered}/{session.total_questions}",
        "current_question_index": session.current_question_index,
        "is_complete": session.is_complete,
        "sufficient_evidence": session.sufficient_evidence,
        "termination_reason": session.termination_reason,
    }
