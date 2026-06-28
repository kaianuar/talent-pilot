"""Complete LangGraph graph builder for screening workflow.

This module creates the full LangGraph workflow that orchestrates
the hexagonal domain layer.
"""

from typing import Any, TypedDict, Annotated, Optional, Literal
from dataclasses import dataclass
from datetime import datetime
import operator

from langgraph.graph import StateGraph, END
from langgraph.checkpoint import BaseCheckpointSaver

from backend.domain.entities.screening_session import (
    ScreeningSession,
    ScreeningStatus,
)
from backend.domain.value_objects.question import Question, Answer
from backend.domain.value_objects.assessment import (
    AnswerAssessment,
    AssessmentDecision,
)
from backend.application.ports.question_generator import QuestionGenerator
from backend.domain.services.answer_assessor import AnswerAssessor


# === Import State Schema ===
# Use single source of truth from langgraph_schema
from backend.infrastructure.orchestration.langgraph_schema import (
    ScreeningGraphState,
    create_initial_state,
    get_screening_summary,
)

# === Import Node Functions ===
# Import node implementations from screening_graph
from backend.infrastructure.orchestration.screening_graph import (
    draft_email_node,
)


# === Node Implementations ===
# Each node receives state, delegates to domain, returns state updates

def create_question_node(
    question_generator: QuestionGenerator,
) -> callable:
    """Factory for question generation node.
    
    This node:
    1. Checks if we need a regular question or a probe
    2. Generates the appropriate question
    3. Updates the ScreeningSession aggregate
    4. Returns state with the question text
    """
    
    def _node(state: ScreeningGraphState) -> ScreeningGraphState:
        print(f"🤖 [Node: generate_question] Generating question...")
        
        session = state["screening_session"]
        
        # Check if we need a probe question (previous assessment was PROBE_FOR_CLARITY)
        current_idx = session.current_question_index
        if current_idx < len(session.question_nodes):
            current_node = session.question_nodes[current_idx]
            
            if (current_node.assessment and 
                current_node.assessment.decision == AssessmentDecision.PROBE_FOR_CLARITY):
                
                # Generate probe question
                print(f"  📍 Previous answer was vague, generating probe...")
                original_question = current_node.question
                previous_answer = current_node.answer
                
                if previous_answer:
                    probe_question = question_generator.generate_follow_up_probe(
                        original_question=original_question,
                        vague_answer=previous_answer.text,
                        context={"tier": session.match_tier},
                    )
                    
                    # Replace current question with probe
                    session.question_nodes[current_idx] = QuestionNode(question=probe_question)
                    
                    return {
                        **state,
                        "generated_question_text": probe_question.text,
                        "current_node": "question_ready",
                        "last_updated": datetime.utcnow(),
                    }
        
        # Standard question flow
        if session.current_question:
            question = session.current_question
            print(f"  ✅ Using question #{session.current_question_index + 1}")
            
            # Mark as asked
            session.ask_current_question()
            
            return {
                **state,
                "generated_question_text": question.text,
                "current_node": "awaiting_answer",
                "last_updated": datetime.utcnow(),
            }
        
        # No more questions - should not reach here normally
        print(f"  ⚠️ No current question available")
        return {
            **state,
            "current_node": "error",
            "error": {"message": "No question available"},
            "last_updated": datetime.utcnow(),
        }
    
    return _node


def receive_answer_node(state: ScreeningGraphState, user_input: str) -> ScreeningGraphState:
    """Node: Receive and record the candidate's answer.
    
    This node is called with the user's answer text and records it
    in the ScreeningSession aggregate.
    """
    print(f"📝 [Node: receive_answer] Recording answer...")
    
    session = state["screening_session"]
    
    # Create answer value object
    answer = Answer(
        question_id=session.current_question.id if session.current_question else "",
        text=user_input,
        timestamp=datetime.utcnow().timestamp(),
    )
    
    # Record in domain entity
    session.record_answer(answer)
    
    print(f"  ✅ Answer recorded ({answer.word_count()} words)")
    
    return {
        **state,
        "user_input": user_input,
        "current_node": "assessing",
        "last_updated": datetime.utcnow(),
    }


def create_assess_answer_node(
    answer_assessor: AnswerAssessor,
) -> callable:
    """Factory for answer assessment node.
    
    This node:
    1. Calls the AnswerAssessor domain service
    2. Records the assessment in the ScreeningSession
    3. Returns state with assessment result
    """
    
    def _node(state: ScreeningGraphState) -> ScreeningGraphState:
        print(f"📊 [Node: assess_answer] Assessing answer...")
        
        session = state["screening_session"]
        
        # Get current question and answer
        current_idx = session.current_question_index
        if current_idx >= len(session.question_nodes):
            print(f"  ⚠️ Invalid question index")
            return {
                **state,
                "current_node": "error",
                "error": {"message": "Invalid question index"},
                "last_updated": datetime.utcnow(),
            }
        
        node = session.question_nodes[current_idx]
        question = node.question
        answer = node.answer
        
        if not answer:
            print(f"  ⚠️ No answer to assess")
            return {
                **state,
                "current_node": "error",
                "error": {"message": "No answer to assess"},
                "last_updated": datetime.utcnow(),
            }
        
        # Assess using domain service
        try:
            assessment = answer_assessor.assess(
                question=question,
                answer=answer,
                context={
                    "tier": session.match_tier,
                    "questions_so_far": session.questions_answered,
                },
            )
            
            # Record assessment in session aggregate
            session.record_assessment(assessment)
            
            print(f"  ✅ Assessment: {assessment.quality.value} → {assessment.decision.value}")
            print(f"     Confidence: {assessment.confidence:.2f}")
            print(f"     Reasoning: {assessment.reasoning[:100]}...")
            
            return {
                **state,
                "assessment": assessment,
                "current_node": "routing",
                "last_updated": datetime.utcnow(),
            }
            
        except Exception as e:
            print(f"  ❌ Assessment failed: {e}")
            return {
                **state,
                "current_node": "error",
                "error": {"message": f"Assessment failed: {e}"},
                "last_updated": datetime.utcnow(),
            }
    
    return _node


# === Conditional Routing ===

def route_after_assessment(state: ScreeningGraphState) -> Literal["ask_question", "probe", "draft_email", "end", "error"]:
    """Conditional edge: Determine next step after assessment.
    
    This function inspects the session state and assessment to decide
    where to route the workflow next.
    """
    session = state["screening_session"]
    
    # Check for errors
    if state.get("error"):
        return "error"
    
    # Check if screening is complete
    if session.is_complete:
        print(f"🏁 [Router] Screening complete: {session.status.value}")
        return "end"
    
    # Check assessment decision
    current_idx = session.current_question_index
    if current_idx < len(session.question_nodes):
        node = session.question_nodes[current_idx]
        if node.assessment:
            decision = node.assessment.decision
            
            if decision == AssessmentDecision.SKIP_TO_EMAIL:
                print(f"📧 [Router] Strong answer → skip to email")
                return "draft_email"
            
            elif decision == AssessmentDecision.PROBE_FOR_CLARITY:
                print(f"🔍 [Router] Vague answer → generate probe")
                return "probe"
            
            elif decision == AssessmentDecision.REJECT_CANDIDATE:
                print(f"❌ [Router] Candidate rejected")
                return "end"
            
            else:  # PROCEED_TO_NEXT_QUESTION
                print(f"➡️  [Router] Proceed to next question")
                return "ask_question"
    
    # Default: ask another question
    print(f"➡️  [Router] Default → ask question")
    return "ask_question"


# === Graph Factory ===

def create_screening_workflow(
    question_generator: QuestionGenerator,
    answer_assessor: AnswerAssessor,
    checkpointer=None,
) -> StateGraph:
    """Create and configure the complete screening workflow.
    
    This factory function wires together all nodes, edges, and conditional
    routing to create the executable screening workflow.
    
    Args:
        question_generator: Port implementation for question generation
        answer_assessor: Domain service for answer assessment
        checkpointer: Optional checkpointer for persistence
        
    Returns:
        Compiled StateGraph ready for execution
    """
    
    # Create the graph
    workflow = StateGraph(ScreeningGraphState)
    
    # Create node callables (with dependencies injected)
    generate_question = create_question_node(question_generator)
    assess_answer = create_assess_answer_node(answer_assessor)
    
    # Add nodes to graph
    workflow.add_node("generate_question", generate_question)
    workflow.add_node("awaiting_answer", receive_answer_node)
    workflow.add_node("assessing", assess_answer)
    workflow.add_node("draft_email", draft_email_node)
    # Error handler node
    workflow.add_node("error", lambda state: {
        **state,
        "current_node": END,
    })
    
    # Add edges
    # Entry point
    workflow.set_entry_point("generate_question")
    
    # Generate question → await answer
    workflow.add_edge("generate_question", "awaiting_answer")
    
    # Awaiting answer → assessing (this is where human input comes in)
    # Note: In practice, this edge is triggered by user input, not automatic
    workflow.add_edge("awaiting_answer", "assessing")
    
    # Assessing → conditional routing
    workflow.add_conditional_edges(
        "assessing",
        route_after_assessment,
        {
            "ask_question": "generate_question",
            "probe": "generate_question",  # Would go to probe generator node
            "draft_email": "draft_email",
            "end": END,
            "error": "error",
        },
    )
    
    # Draft email → end
    workflow.add_edge("draft_email", END)
    
    # Error → end
    workflow.add_edge("error", END)
    
    # Compile with optional checkpointer
    if checkpointer:
        return workflow.compile(checkpointer=checkpointer)
    
    return workflow.compile()


# === Execution Helpers ===

async def run_screening_interactive(
    workflow: StateGraph,
    session: ScreeningSession,
    input_callback: Callable[[str], str],
    output_callback: Callable[[str], None],
):
    """Run a screening session with interactive user input.
    
    This is the main entry point for running a screening session.
    It handles the back-and-forth between the graph and the user.
    
    Args:
        workflow: The compiled LangGraph workflow
        session: The initialized ScreeningSession aggregate
        input_callback: Function to get user input (e.g., from CLI, WebSocket, etc.)
        output_callback: Function to output text to the user
    """
    from langgraph.types import Interrupt
    
    # Create initial state
    initial_state = create_initial_state(session)
    
    # Stream the graph execution
    output_callback("🎯 Starting screening session...")
    
    async for event in workflow.astream(initial_state):
        # Handle different event types
        if event["event"] == "on_chain_start":
            continue
        
        if event["event"] == "on_chain_end":
            # Check if we're waiting for user input
            state = event["data"]["output"]
            
            if state.get("current_node") == "awaiting_answer":
                question_text = state.get("generated_question_text", "Please respond:")
                
                # Output the question
                output_callback(f"\n🤖 {question_text}")
                output_callback("⏳ Waiting for your answer...")
                
                # Get user input
                user_response = input_callback("Your answer: ")
                
                # Continue with user response
                # This would typically be done by updating state and resuming
                # For now, we'll handle it synchronously
                
                # Create updated state with user input
                updated_state = {
                    **state,
                    "user_input": user_response,
                }
                
                # Continue the workflow
                # Note: In a real implementation, this would use LangGraph's
                # interrupt/resume mechanism
                
            elif state.get("current_node") == END:
                output_callback("\n✅ Screening session complete!")
                break


def run_screening_sync(
    workflow: StateGraph,
    session: ScreeningSession,
    user_inputs: list[str],
) -> dict:
    """Run a screening session synchronously with pre-defined inputs.
    
    Useful for testing or batch processing.
    
    Args:
        workflow: The compiled LangGraph workflow
        session: The initialized ScreeningSession aggregate
        user_inputs: List of user answers to use
        
    Returns:
        Final state after completion
    """
    from langgraph.types import Command
    
    # Create initial state
    state = create_initial_state(session)
    
    # Track input index
    input_idx = 0
    
    # Run until complete
    while True:
        # Run one step
        result = workflow.invoke(state)
        
        # Check if we need user input
        if result.get("current_node") == "awaiting_answer":
            if input_idx >= len(user_inputs):
                raise ValueError(f"Need more user inputs (have {len(user_inputs)}, need more)")
            
            # Inject user input
            result["user_input"] = user_inputs[input_idx]
            input_idx += 1
        
        # Update state for next iteration
        state = result
        
        # Check if complete
        if result.get("current_node") == END or result.get("current_node") == "end":
            break
    
    return state


# === Convenience Exports ===

__all__ = [
    # Graph factory
    "create_screening_workflow",
    # Execution helpers
    "run_screening_interactive",
    "run_screening_sync",
    # State helpers
    "create_initial_state",
    # Export types
    "ScreeningGraphState",
]
