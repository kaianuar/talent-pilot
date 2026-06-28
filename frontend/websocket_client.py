"""WebSocket client for real-time screening progress updates.

This module provides a simple WebSocket client for connecting to the
backend's WebSocket endpoint and receiving real-time progress updates.
Designed to work with Streamlit's async capabilities.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable, List
from enum import Enum

import websockets


logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """WebSocket connection state."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class ProgressUpdate:
    """Screening progress update from WebSocket."""
    message_type: str
    screening_id: str
    candidate_id: str
    status: str
    current_question_number: int
    total_questions: int
    progress_percentage: float
    current_question: Optional[Dict[str, Any]] = None
    latest_assessment: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    timestamp: str = ""


@dataclass
class WebSocketConfig:
    """WebSocket client configuration."""
    base_url: str = "ws://localhost:9000"
    reconnect_attempts: int = 3
    reconnect_delay: float = 1.0
    heartbeat_interval: float = 30.0
    message_timeout: float = 5.0


class ScreeningWebSocketClient:
    """WebSocket client for screening progress updates.
    
    This client connects to the backend WebSocket endpoint and receives
    real-time progress updates during the screening process.
    
    Example usage:
        client = ScreeningWebSocketClient()
        
        # Set up callbacks
        client.on_progress(lambda update: print(f"Progress: {update.progress_percentage}%"))
        client.on_error(lambda msg: print(f"Error: {msg}"))
        
        # Connect and subscribe
        await client.connect("screening-123", "candidate-456")
        
        # Listen for updates
        await client.listen()
    """
    
    def __init__(
        self,
        config: Optional[WebSocketConfig] = None,
    ):
        """Initialize the WebSocket client.
        
        Args:
            config: WebSocket configuration (uses defaults if not provided)
        """
        self.config = config or WebSocketConfig()
        
        # Connection state
        self._state = ConnectionState.DISCONNECTED
        self._websocket: Optional[websockets.WebSocketClientProtocol] = None
        self._screening_id: Optional[str] = None
        self._candidate_id: Optional[str] = None
        
        # Reconnection state
        self._reconnect_attempts = 0
        self._should_reconnect = True
        
        # Callbacks
        self._progress_callbacks: List[Callable[[ProgressUpdate], None]] = []
        self._error_callbacks: List[Callable[[str], None]] = []
        self._connect_callbacks: List[Callable[[], None]] = []
        self._disconnect_callbacks: List[Callable[[], None]] = []
        
        logger.info("ScreeningWebSocketClient initialized")
    
    # Callback registration methods
    def on_progress(self, callback: Callable[[ProgressUpdate], None]) -> None:
        """Register a callback for progress updates.
        
        Args:
            callback: Function to call when progress updates are received
        """
        self._progress_callbacks.append(callback)
    
    def on_error(self, callback: Callable[[str], None]) -> None:
        """Register a callback for error messages.
        
        Args:
            callback: Function to call when errors occur
        """
        self._error_callbacks.append(callback)
    
    def on_connect(self, callback: Callable[[], None]) -> None:
        """Register a callback for connection establishment.
        
        Args:
            callback: Function to call when connection is established
        """
        self._connect_callbacks.append(callback)
    
    def on_disconnect(self, callback: Callable[[], None]) -> None:
        """Register a callback for disconnection.
        
        Args:
            callback: Function to call when connection is closed
        """
        self._disconnect_callbacks.append(callback)
    
    # Properties
    @property
    def state(self) -> ConnectionState:
        """Get current connection state."""
        return self._state
    
    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._state == ConnectionState.CONNECTED
    
    # Connection methods
    async def connect(
        self,
        screening_id: str,
        candidate_id: str,
    ) -> bool:
        """Connect to WebSocket and subscribe to screening updates.
        
        Args:
            screening_id: The screening session ID to subscribe to
            candidate_id: The candidate ID
            
        Returns:
            True if connection successful, False otherwise
        """
        self._screening_id = screening_id
        self._candidate_id = candidate_id
        self._should_reconnect = True
        
        return await self._do_connect()
    
    async def _do_connect(self) -> bool:
        """Internal method to establish WebSocket connection."""
        if self._state == ConnectionState.CONNECTED:
            return True
        
        self._state = ConnectionState.CONNECTING
        
        try:
            ws_url = (
                f"{self.config.base_url}/ws/screening/{self._screening_id}"
                f"?candidate_id={self._candidate_id}"
            )
            
            logger.info(f"Connecting to WebSocket: {ws_url}")
            
            self._websocket = await websockets.connect(ws_url)
            self._state = ConnectionState.CONNECTED
            self._reconnect_attempts = 0
            
            # Notify callbacks
            for callback in self._connect_callbacks:
                try:
                    callback()
                except Exception as e:
                    logger.error(f"Error in connect callback: {e}")
            
            logger.info("WebSocket connected successfully")
            return True
            
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            self._state = ConnectionState.ERROR
            
            # Notify error callbacks
            for callback in self._error_callbacks:
                try:
                    callback(f"Connection failed: {str(e)}")
                except Exception:
                    pass
            
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from WebSocket."""
        self._should_reconnect = False
        
        if self._websocket:
            try:
                await self._websocket.close()
            except Exception as e:
                logger.debug(f"Error closing WebSocket: {e}")
            finally:
                self._websocket = None
        
        self._state = ConnectionState.DISCONNECTED
        
        # Notify callbacks
        for callback in self._disconnect_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in disconnect callback: {e}")
        
        logger.info("WebSocket disconnected")
    
    # Message handling
    async def listen(self) -> None:
        """Listen for messages from the WebSocket.
        
        This method should be called after connect() to start
        receiving messages. It will continue until disconnect()
        is called or the connection is lost.
        """
        if not self._websocket:
            raise RuntimeError("WebSocket not connected. Call connect() first.")
        
        try:
            async for message in self._websocket:
                await self._handle_message(message)
                
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed by server")
            
            # Attempt reconnection if enabled
            if self._should_reconnect:
                await self._attempt_reconnect()
                
        except Exception as e:
            logger.exception(f"Error in WebSocket listener: {e}")
            
            # Notify error callbacks
            for callback in self._error_callbacks:
                try:
                    callback(f"Listener error: {str(e)}")
                except Exception:
                    pass
    
    async def _handle_message(self, message: str) -> None:
        """Handle an incoming WebSocket message."""
        try:
            data = json.loads(message)
            
            message_type = data.get("message_type", "unknown")
            
            if message_type == "heartbeat":
                # Respond to heartbeat
                await self._send_heartbeat_ack()
                return
            
            if message_type == "connected":
                logger.info(f"WebSocket connection confirmed: {data.get('message')}")
                return
            
            # Parse progress update
            progress = ProgressUpdate(
                message_type=message_type,
                screening_id=data.get("screening_id", ""),
                candidate_id=data.get("candidate_id", ""),
                status=data.get("status", ""),
                current_question_number=data.get("current_question_number", 0),
                total_questions=data.get("total_questions", 0),
                progress_percentage=data.get("progress_percentage", 0.0),
                timestamp=data.get("timestamp", ""),
            )
            
            # Parse optional fields
            if "current_question" in data:
                q = data["current_question"]
                progress.current_question = Question(
                    id=q.get("id", ""),
                    text=q.get("text", ""),
                    type=q.get("type", ""),
                    focus_area=q.get("focus_area", ""),
                    expected_evidence=q.get("expected_evidence", []),
                    priority=q.get("priority", "REQUIRED"),
                )
            
            if "latest_assessment" in data:
                a = data["latest_assessment"]
                progress.latest_assessment = Assessment(
                    quality=a.get("quality", ""),
                    confidence=a.get("confidence", 0.0),
                    key_points_identified=a.get("key_points_identified", []),
                    gaps_identified=a.get("gaps_identified", []),
                    decision=a.get("decision", ""),
                    reasoning=a.get("reasoning", ""),
                )
            
            if "error_message" in data:
                progress.error_message = data["error_message"]
            
            # Notify callbacks
            for callback in self._progress_callbacks:
                try:
                    callback(progress)
                except Exception as e:
                    logger.error(f"Error in progress callback: {e}")
                    
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from WebSocket: {e}")
        except Exception as e:
            logger.exception(f"Error handling WebSocket message: {e}")
    
    async def _send_heartbeat_ack(self) -> None:
        """Send heartbeat acknowledgment."""
        if self._websocket:
            try:
                await self._websocket.send(json.dumps({
                    "type": "heartbeat_ack",
                    "timestamp": asyncio.get_event_loop().time(),
                }))
            except Exception as e:
                logger.debug(f"Failed to send heartbeat ack: {e}")
    
    async def _attempt_reconnect(self) -> bool:
        """Attempt to reconnect to the WebSocket.
        
        Returns:
            True if reconnection successful, False otherwise
        """
        if self._reconnect_attempts >= self.config.reconnect_attempts:
            logger.error("Max reconnection attempts reached")
            
            for callback in self._error_callbacks:
                try:
                    callback("Max reconnection attempts reached")
                except Exception:
                    pass
            
            return False
        
        self._reconnect_attempts += 1
        self._state = ConnectionState.RECONNECTING
        
        logger.info(f"Attempting to reconnect ({self._reconnect_attempts}/{self.config.reconnect_attempts})...")
        
        # Wait before reconnecting
        await asyncio.sleep(self.config.reconnect_delay * self._reconnect_attempts)
        
        # Attempt to reconnect
        success = await self._do_connect()
        
        if success:
            logger.info("Reconnection successful")
            return True
        else:
            # Try again if not reached max attempts
            return await self._attempt_reconnect()
    
    # Convenience methods for Streamlit
    def get_sync_client(self):
        """Get a synchronous wrapper for use in Streamlit.
        
        Streamlit doesn't support async directly in the main thread,
        so this wrapper provides synchronous versions of the methods.
        """
        return SyncGRPCWebClient(self)


class SyncGRPCWebClient:
    """Synchronous wrapper for GRPCWebClient.
    
    This wrapper provides synchronous versions of the async methods,
    making it easier to use from Streamlit which doesn't support
    async in the main thread.
    """
    
    def __init__(self, async_client: GRPCWebClient):
        """Initialize with an async client.
        
        Args:
            async_client: The async GRPCWebClient to wrap
        """
        self._client = async_client
        self._loop = asyncio.new_event_loop()
    
    def _run_async(self, coro):
        """Run an async coroutine synchronously."""
        return self._loop.run_until_complete(coro)
    
    def start_screening(
        self,
        candidate_id: str,
        job_id: str,
        match_tier: str,
        question_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Start a new screening session (sync version)."""
        return self._run_async(
            self._client.start_screening(
                candidate_id, job_id, match_tier, question_count
            )
        )
    
    def submit_answer(
        self,
        screening_id: str,
        candidate_id: str,
        question_id: str,
        answer_text: str,
        response_time_seconds: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Submit an answer (sync version)."""
        return self._run_async(
            self._client.submit_answer(
                screening_id, candidate_id, question_id, answer_text, response_time_seconds
            )
        )
    
    def close(self) -> None:
        """Close the client and release resources."""
        if self._loop and not self._loop.is_closed():
            self._loop.close()
