"""gRPC-Web client for browser-based screening operations.

This module provides a Python-based client that mirrors what would be
a TypeScript/JavaScript gRPC-Web client in a real browser application.
It supports both gRPC-Web for RPC calls and WebSocket for real-time updates.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable, List, AsyncIterator, Union
from enum import Enum
import websockets
import httpx


logger = logging.getLogger(__name__)


class ScreeningStatus(Enum):
    """Screening session status."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"
    EARLY_TERMINATION = "EARLY_TERMINATION"
    REJECTED = "REJECTED"
    ERROR = "ERROR"


@dataclass
class Question:
    """Screening question."""
    id: str
    text: str
    type: str
    focus_area: str
    expected_evidence: List[str] = field(default_factory=list)
    priority: str = "REQUIRED"


@dataclass
class Assessment:
    """Answer assessment."""
    quality: str
    confidence: float
    key_points_identified: List[str] = field(default_factory=list)
    gaps_identified: List[str] = field(default_factory=list)
    decision: str = "PROCEED_TO_NEXT_QUESTION"
    reasoning: str = ""


@dataclass
class EmailDraft:
    """Email draft for recruiter."""
    to: str
    subject: str
    body: str
    cc: str = ""
    bcc: str = ""


@dataclass
class ScreeningResult:
    """Complete screening result."""
    screening_id: str
    candidate_id: str
    job_id: str
    status: ScreeningStatus
    total_questions_asked: int
    average_answer_quality: float
    final_assessment: str
    sufficient_evidence: bool
    email_draft: Optional[EmailDraft] = None


@dataclass
class ProgressUpdate:
    """Real-time progress update."""
    message_type: str
    screening_id: str
    candidate_id: str
    status: str
    current_question_number: int
    total_questions: int
    progress_percentage: float
    current_question: Optional[Question] = None
    latest_assessment: Optional[Assessment] = None
    error_message: Optional[str] = None
    timestamp: str = ""


class GRPCWebClient:
    """gRPC-Web client for screening operations.
    
    This client provides both gRPC-Web style RPC calls and WebSocket
    real-time updates, similar to what a TypeScript/JavaScript client
    would provide in a real browser application.
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:9000",
        grpc_web_path: str = "/grpc-web",
        ws_base_url: str = "ws://localhost:9000",
        timeout: float = 30.0,
    ):
        """Initialize the gRPC-Web client.
        
        Args:
            base_url: Base URL for HTTP/gRPC-Web requests
            grpc_web_path: Path for gRPC-Web requests
            ws_base_url: Base URL for WebSocket connections
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.grpc_web_path = grpc_web_path
        self.ws_base_url = ws_base_url
        self.timeout = timeout
        
        # HTTP client for gRPC-Web requests
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            http2=True,  # Enable HTTP/2 for gRPC
        )
        
        # WebSocket connection
        self._ws_connection: Optional[websockets.WebSocketClientProtocol] = None
        self._ws_task: Optional[asyncio.Task] = None
        
        # Callbacks for real-time updates
        self._progress_callbacks: List[Callable[[ProgressUpdate], None]] = []
        self._error_callbacks: List[Callable[[str], None]] = []
        
        logger.info(f"GRPCWebClient initialized: {base_url}, {ws_base_url}")
    
    def add_progress_callback(self, callback: Callable[[ProgressUpdate], None]) -> None:
        """Add a callback for progress updates.
        
        Args:
            callback: Function to call when progress updates are received
        """
        self._progress_callbacks.append(callback)
    
    def add_error_callback(self, callback: Callable[[str], None]) -> None:
        """Add a callback for error messages.
        
        Args:
            callback: Function to call when errors occur
        """
        self._error_callbacks.append(callback)
    
    async def start_screening(
        self,
        candidate_id: str,
        job_id: str,
        match_tier: str,
        question_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Start a new screening session.
        
        Args:
            candidate_id: The candidate ID
            job_id: The job ID
            match_tier: Match tier (STRONG_MATCH, PARTIAL_MATCH, WEAK_MATCH)
            question_count: Optional number of questions
            
        Returns:
            Dictionary with screening_id, first_question, and success status
        """
        url = f"{self.base_url}{self.grpc_web_path}/talentpilot.screening.ScreeningService/StartScreening"
        
        request_data = {
            "candidate_id": candidate_id,
            "job_id": job_id,
            "match_tier": match_tier,
        }
        
        if question_count is not None:
            request_data["question_count"] = question_count
        
        try:
            response = await self._http_client.post(
                url,
                json=request_data,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"StartScreening successful: {result.get('screening_id')}")
            return result
            
        except httpx.HTTPStatusError as e:
            logger.error(f"StartScreening HTTP error: {e}")
            return {
                "success": False,
                "error_message": f"HTTP error: {e.response.status_code}",
            }
        except Exception as e:
            logger.exception("StartScreening failed")
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
    ) -> Dict[str, Any]:
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
        url = f"{self.base_url}{self.grpc_web_path}/talentpilot.screening.ScreeningService/SubmitAnswer"
        
        request_data = {
            "screening_id": screening_id,
            "candidate_id": candidate_id,
            "question_id": question_id,
            "answer_text": answer_text,
        }
        
        if response_time_seconds is not None:
            request_data["response_time_seconds"] = response_time_seconds
        
        try:
            response = await self._http_client.post(
                url,
                json=request_data,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            
            response.raise_for_status()
            result = response.json()
            
            logger.info(f"SubmitAnswer successful for screening {screening_id}")
            return result
            
        except httpx.HTTPStatusError as e:
            logger.error(f"SubmitAnswer HTTP error: {e}")
            return {
                "success": False,
                "error_message": f"HTTP error: {e.response.status_code}",
            }
        except Exception as e:
            logger.exception("SubmitAnswer failed")
            return {
                "success": False,
                "error_message": str(e),
            }
    
    async def connect_websocket(
        self,
        screening_id: str,
        candidate_id: str,
    ) -> None:
        """Connect to WebSocket for real-time progress updates.
        
        Args:
            screening_id: The screening session ID to subscribe to
            candidate_id: The candidate ID
        """
        ws_url = f"{self.ws_base_url}/ws/screening/{screening_id}?candidate_id={candidate_id}"
        
        try:
            self._ws_connection = await websockets.connect(ws_url)
            logger.info(f"WebSocket connected: {ws_url}")
            
            # Start listening for messages
            self._ws_task = asyncio.create_task(self._listen_websocket())
            
        except Exception as e:
            logger.exception(f"WebSocket connection failed: {e}")
            for callback in self._error_callbacks:
                callback(f"WebSocket connection failed: {e}")
    
    async def _listen_websocket(self) -> None:
        """Listen for WebSocket messages and dispatch to callbacks."""
        if not self._ws_connection:
            return
        
        try:
            async for message in self._ws_connection:
                try:
                    data = json.loads(message)
                    
                    # Create ProgressUpdate from message
                    progress = ProgressUpdate(
                        message_type=data.get("message_type", "unknown"),
                        screening_id=data.get("screening_id", ""),
                        candidate_id=data.get("candidate_id", ""),
                        status=data.get("status", ""),
                        current_question_number=data.get("current_question_number", 0),
                        total_questions=data.get("total_questions", 0),
                        progress_percentage=data.get("progress_percentage", 0.0),
                        timestamp=data.get("timestamp", ""),
                    )
                    
                    # Dispatch to callbacks
                    for callback in self._progress_callbacks:
                        callback(progress)
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON from WebSocket: {e}")
                except Exception as e:
                    logger.exception(f"Error processing WebSocket message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
        except Exception as e:
            logger.exception(f"WebSocket error: {e}")
            for callback in self._error_callbacks:
                callback(f"WebSocket error: {e}")
    
    async def disconnect_websocket(self) -> None:
        """Disconnect from WebSocket."""
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
            self._ws_task = None
        
        if self._ws_connection:
            await self._ws_connection.close()
            self._ws_connection = None
        
        logger.info("WebSocket disconnected")
    
    async def close(self) -> None:
        """Close the client and release all resources."""
        await self.disconnect_websocket()
        await self._http_client.aclose()
        logger.info("GRPCWebClient closed")


# Convenience function for creating a client
def create_client(
    base_url: str = "http://localhost:9000",
    ws_base_url: str = "ws://localhost:9000",
) -> GRPCWebClient:
    """Create a new GRPCWebClient with default settings.
    
    Args:
        base_url: Base URL for HTTP/gRPC-Web requests
        ws_base_url: Base URL for WebSocket connections
        
    Returns:
        Configured GRPCWebClient instance
    """
    return GRPCWebClient(
        base_url=base_url,
        ws_base_url=ws_base_url,
    )
