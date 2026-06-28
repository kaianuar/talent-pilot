"""gRPC-Web and WebSocket integration for Streamlit.

This module provides Streamlit-compatible components for interacting
with the backend's gRPC-Web and WebSocket endpoints.
"""

import asyncio
import json
import logging
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass

import streamlit as st

# Import our gRPC-Web client
from frontend.grpc_client import GRPCWebClient, SyncGRPCWebClient, ProgressUpdate
from frontend.websocket_client import ScreeningWebSocketClient, WebSocketConfig


logger = logging.getLogger(__name__)


# Session state keys
SCREENING_ID_KEY = "screening_id"
CANDIDATE_ID_KEY = "candidate_id"
JOB_ID_KEY = "job_id"
WS_CLIENT_KEY = "ws_client"
GRPC_CLIENT_KEY = "grpc_client"
PROGRESS_KEY = "screening_progress"
SCREENING_COMPLETE_KEY = "screening_complete"


@dataclass
class ScreeningState:
    """State for the screening process."""
    screening_id: Optional[str] = None
    candidate_id: Optional[str] = None
    job_id: Optional[str] = None
    progress: float = 0.0
    current_question: Optional[Dict[str, Any]] = None
    total_questions: int = 0
    current_question_number: int = 0
    is_complete: bool = False
    email_draft: Optional[Dict[str, str]] = None


def init_session_state():
    """Initialize Streamlit session state variables."""
    if SCREENING_ID_KEY not in st.session_state:
        st.session_state[SCREENING_ID_KEY] = None
    if CANDIDATE_ID_KEY not in st.session_state:
        st.session_state[CANDIDATE_ID_KEY] = None
    if JOB_ID_KEY not in st.session_state:
        st.session_state[JOB_ID_KEY] = None
    if PROGRESS_KEY not in st.session_state:
        st.session_state[PROGRESS_KEY] = 0.0
    if SCREENING_COMPLETE_KEY not in st.session_state:
        st.session_state[SCREENING_COMPLETE_KEY] = False


def get_screening_state() -> ScreeningState:
    """Get current screening state from session state."""
    return ScreeningState(
        screening_id=st.session_state.get(SCREENING_ID_KEY),
        candidate_id=st.session_state.get(CANDIDATE_ID_KEY),
        job_id=st.session_state.get(JOB_ID_KEY),
        progress=st.session_state.get(PROGRESS_KEY, 0.0),
        is_complete=st.session_state.get(SCREENING_COMPLETE_KEY, False),
    )


def update_screening_state(updates: Dict[str, Any]):
    """Update screening state in session state."""
    for key, value in updates.items():
        st.session_state[key] = value


class StreamlitScreeningClient:
    """High-level client for screening operations in Streamlit.
    
    This client combines gRPC-Web and WebSocket functionality to provide
    a complete screening experience in Streamlit.
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:9000",
        ws_base_url: str = "ws://localhost:9000",
    ):
        """Initialize the screening client.
        
        Args:
            base_url: Base URL for HTTP/gRPC-Web requests
            ws_base_url: Base URL for WebSocket connections
        """
        self.base_url = base_url
        self.ws_base_url = ws_base_url
        
        # Initialize clients
        async_client = GRPCWebClient(
            base_url=base_url,
            ws_base_url=ws_base_url,
        )
        self.grpc_client = async_client.get_sync_client()
        
        # WebSocket client (initialized on demand)
        self.ws_client: Optional[ScreeningWebSocketClient] = None
        
        logger.info("StreamlitScreeningClient initialized")
    
    def start_screening(
        self,
        candidate_id: str,
        job_id: str,
        match_tier: str,
        question_count: Optional[int] = None,
    ) -> Optional[str]:
        """Start a new screening session.
        
        Args:
            candidate_id: The candidate ID
            job_id: The job ID
            match_tier: Match tier (STRONG_MATCH, PARTIAL_MATCH, WEAK_MATCH)
            question_count: Optional number of questions
            
        Returns:
            Screening ID if successful, None otherwise
        """
        try:
            result = self.grpc_client.start_screening(
                candidate_id=candidate_id,
                job_id=job_id,
                match_tier=match_tier,
                question_count=question_count,
            )
            
            if result.get("success"):
                screening_id = result["screening_id"]
                
                # Update session state
                update_screening_state({
                    SCREENING_ID_KEY: screening_id,
                    CANDIDATE_ID_KEY: candidate_id,
                    JOB_ID_KEY: job_id,
                })
                
                logger.info(f"Screening started: {screening_id}")
                return screening_id
            else:
                error = result.get("error_message", "Unknown error")
                logger.error(f"Failed to start screening: {error}")
                st.error(f"Failed to start screening: {error}")
                return None
                
        except Exception as e:
            logger.exception("Error starting screening")
            st.error(f"Error starting screening: {e}")
            return None
    
    def submit_answer(
        self,
        question_id: str,
        answer_text: str,
        response_time_seconds: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Submit an answer.
        
        Args:
            question_id: The question ID
            answer_text: The answer text
            response_time_seconds: Optional response time
            
        Returns:
            Result dictionary if successful, None otherwise
        """
        screening_id = st.session_state.get(SCREENING_ID_KEY)
        candidate_id = st.session_state.get(CANDIDATE_ID_KEY)
        
        if not screening_id or not candidate_id:
            st.error("No active screening session")
            return None
        
        try:
            result = self.grpc_client.submit_answer(
                screening_id=screening_id,
                candidate_id=candidate_id,
                question_id=question_id,
                answer_text=answer_text,
                response_time_seconds=response_time_seconds,
            )
            
            # Update progress
            if result.get("is_complete"):
                update_screening_state({
                    SCREENING_COMPLETE_KEY: True,
                    PROGRESS_KEY: 100.0,
                })
            
            logger.info(f"Answer submitted for screening {screening_id}")
            return result
            
        except Exception as e:
            logger.exception("Error submitting answer")
            st.error(f"Error submitting answer: {e}")
            return None
    
    def close(self):
        """Close the client and release resources."""
        if self.grpc_client:
            self.grpc_client.close()
        logger.info("StreamlitScreeningClient closed")


# Convenience function for Streamlit
def get_screening_client(
    base_url: str = "http://localhost:9000",
    ws_base_url: str = "ws://localhost:9000",
) -> StreamlitScreeningClient:
    """Get or create a StreamlitScreeningClient instance.
    
    Args:
        base_url: Base URL for HTTP/gRPC-Web requests
        ws_base_url: Base URL for WebSocket connections
        
    Returns:
        StreamlitScreeningClient instance
    """
    # Use Streamlit's session state to persist the client
    client_key = "screening_client"
    
    if client_key not in st.session_state:
        st.session_state[client_key] = StreamlitScreeningClient(
            base_url=base_url,
            ws_base_url=ws_base_url,
        )
    
    return st.session_state[client_key]
