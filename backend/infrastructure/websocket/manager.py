"""WebSocket connection manager for real-time screening progress updates.

This module provides WebSocket support for broadcasting screening progress
updates to connected clients in real-time, complementing the gRPC service.
"""

import asyncio
import json
import logging
from typing import Dict, List, Set, Optional, Any, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum

from fastapi import WebSocket, WebSocketDisconnect


logger = logging.getLogger(__name__)


class ScreeningStatus(str, Enum):
    """Screening status for WebSocket updates."""
    STARTED = "STARTED"
    QUESTION_ASKED = "QUESTION_ASKED"
    ANSWER_RECEIVED = "ANSWER_RECEIVED"
    ASSESSING = "ASSESSING"
    COMPLETE = "COMPLETE"
    EARLY_TERMINATION = "EARLY_TERMINATION"
    REJECTED = "REJECTED"
    ERROR = "ERROR"


@dataclass
class QuestionData:
    """Question data for WebSocket messages."""
    id: str
    text: str
    type: str
    focus_area: str
    expected_evidence: List[str]
    priority: str


@dataclass
class AssessmentData:
    """Assessment data for WebSocket messages."""
    quality: str
    confidence: float
    key_points_identified: List[str]
    gaps_identified: List[str]
    decision: str
    reasoning: str


@dataclass
class ScreeningProgressMessage:
    """Screening progress message for WebSocket broadcast."""
    message_type: str  # "progress", "question", "assessment", "complete", "error"
    screening_id: str
    candidate_id: str
    status: str
    current_question_number: int
    total_questions: int
    progress_percentage: float
    current_question: Optional[QuestionData] = None
    latest_assessment: Optional[AssessmentData] = None
    error_message: Optional[str] = None
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat() + "Z"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for JSON serialization."""
        result = {
            "message_type": self.message_type,
            "screening_id": self.screening_id,
            "candidate_id": self.candidate_id,
            "status": self.status,
            "current_question_number": self.current_question_number,
            "total_questions": self.total_questions,
            "progress_percentage": self.progress_percentage,
            "timestamp": self.timestamp,
        }
        
        if self.current_question:
            result["current_question"] = asdict(self.current_question)
        if self.latest_assessment:
            result["latest_assessment"] = asdict(self.latest_assessment)
        if self.error_message:
            result["error_message"] = self.error_message
            
        return result
    
    def to_json(self) -> str:
        """Convert message to JSON string."""
        return json.dumps(self.to_dict())


class ConnectionManager:
    """Manages WebSocket connections for real-time screening progress updates.
    
    This manager handles:
    - Connection lifecycle (connect/disconnect)
    - Subscription management (screening_id-based routing)
    - Broadcast messaging (progress updates)
    - Connection health monitoring
    """
    
    def __init__(self):
        """Initialize the connection manager."""
        # All active connections
        self._connections: Dict[str, WebSocket] = {}
        
        # Connection ID -> screening_id subscriptions
        self._subscriptions: Dict[str, str] = {}
        
        # Screening_id -> set of connection IDs
        self._screening_subscribers: Dict[str, Set[str]] = {}
        
        # Callbacks for various events
        self._on_connect: Optional[Callable[[str, WebSocket], None]] = None
        self._on_disconnect: Optional[Callable[[str], None]] = None
        self._on_subscribe: Optional[Callable[[str, str], None]] = None
        
        self._connection_counter = 0
        self._lock = asyncio.Lock()
        
        logger.info("ConnectionManager initialized")
    
    def set_callbacks(
        self,
        on_connect: Optional[Callable[[str, WebSocket], None]] = None,
        on_disconnect: Optional[Callable[[str], None]] = None,
        on_subscribe: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        """Set callback functions for connection events.
        
        Args:
            on_connect: Called when a new connection is established
            on_disconnect: Called when a connection is closed
            on_subscribe: Called when a connection subscribes to a screening
        """
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._on_subscribe = on_subscribe
    
    async def connect(self, websocket: WebSocket) -> str:
        """Accept a new WebSocket connection.
        
        Args:
            websocket: The WebSocket object to accept
            
        Returns:
            connection_id: Unique identifier for this connection
        """
        await websocket.accept()
        
        async with self._lock:
            self._connection_counter += 1
            connection_id = f"conn_{self._connection_counter}_{id(websocket)}"
            self._connections[connection_id] = websocket
        
        logger.info(f"WebSocket connection accepted: {connection_id}")
        
        if self._on_connect:
            try:
                self._on_connect(connection_id, websocket)
            except Exception as e:
                logger.error(f"Error in on_connect callback: {e}")
        
        return connection_id
    
    async def disconnect(self, connection_id: str) -> None:
        """Close a WebSocket connection and clean up.
        
        Args:
            connection_id: The connection ID to disconnect
        """
        async with self._lock:
            # Remove from connections
            websocket = self._connections.pop(connection_id, None)
            
            # Remove from subscriptions
            screening_id = self._subscriptions.pop(connection_id, None)
            if screening_id and screening_id in self._screening_subscribers:
                self._screening_subscribers[screening_id].discard(connection_id)
                if not self._screening_subscribers[screening_id]:
                    del self._screening_subscribers[screening_id]
        
        # Close the WebSocket
        if websocket:
            try:
                await websocket.close()
            except Exception as e:
                logger.debug(f"Error closing WebSocket {connection_id}: {e}")
        
        logger.info(f"WebSocket connection disconnected: {connection_id}")
        
        if self._on_disconnect:
            try:
                self._on_disconnect(connection_id)
            except Exception as e:
                logger.error(f"Error in on_disconnect callback: {e}")
    
    async def subscribe(self, connection_id: str, screening_id: str) -> bool:
        """Subscribe a connection to receive updates for a specific screening.
        
        Args:
            connection_id: The connection ID to subscribe
            screening_id: The screening ID to subscribe to
            
        Returns:
            True if subscription successful, False otherwise
        """
        async with self._lock:
            if connection_id not in self._connections:
                logger.error(f"Cannot subscribe: connection {connection_id} not found")
                return False
            
            # Remove from any existing subscription
            old_screening = self._subscriptions.get(connection_id)
            if old_screening and old_screening in self._screening_subscribers:
                self._screening_subscribers[old_screening].discard(connection_id)
            
            # Add new subscription
            self._subscriptions[connection_id] = screening_id
            if screening_id not in self._screening_subscribers:
                self._screening_subscribers[screening_id] = set()
            self._screening_subscribers[screening_id].add(connection_id)
        
        logger.info(f"Connection {connection_id} subscribed to screening {screening_id}")
        
        if self._on_subscribe:
            try:
                self._on_subscribe(connection_id, screening_id)
            except Exception as e:
                logger.error(f"Error in on_subscribe callback: {e}")
        
        return True
    
    async def broadcast_to_screening(
        self,
        screening_id: str,
        message: ScreeningProgressMessage,
    ) -> int:
        """Broadcast a message to all connections subscribed to a screening.
        
        Args:
            screening_id: The screening ID to broadcast to
            message: The message to broadcast
            
        Returns:
            Number of connections the message was sent to
        """
        message_json = message.to_json()
        
        async with self._lock:
            connection_ids = list(self._screening_subscribers.get(screening_id, []))
        
        sent_count = 0
        failed_connections = []
        
        for connection_id in connection_ids:
            websocket = self._connections.get(connection_id)
            if not websocket:
                failed_connections.append(connection_id)
                continue
            
            try:
                await websocket.send_text(message_json)
                sent_count += 1
            except Exception as e:
                logger.warning(f"Failed to send to {connection_id}: {e}")
                failed_connections.append(connection_id)
        
        # Clean up failed connections
        for connection_id in failed_connections:
            await self.disconnect(connection_id)
        
        return sent_count
    
    async def send_to_connection(
        self,
        connection_id: str,
        message: ScreeningProgressMessage,
    ) -> bool:
        """Send a message to a specific connection.
        
        Args:
            connection_id: The connection ID to send to
            message: The message to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        websocket = self._connections.get(connection_id)
        if not websocket:
            return False
        
        try:
            await websocket.send_text(message.to_json())
            return True
        except Exception as e:
            logger.warning(f"Failed to send to {connection_id}: {e}")
            await self.disconnect(connection_id)
            return False
    
    def get_connection_count(self) -> int:
        """Get the total number of active connections."""
        return len(self._connections)
    
    def get_screening_subscriber_count(self, screening_id: str) -> int:
        """Get the number of subscribers for a specific screening."""
        return len(self._screening_subscribers.get(screening_id, set()))
