"""WebSocket routes for real-time screening progress updates.

This module provides WebSocket endpoints for the FastAPI application,
enabling real-time bidirectional communication with connected clients.
"""

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, status

from backend.infrastructure.websocket.manager import (
    ConnectionManager,
    ScreeningProgressMessage,
    QuestionData,
    AssessmentData,
)


logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/ws", tags=["websocket"])

# Global connection manager instance
_connection_manager: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    """Get or create the global connection manager instance.
    
    Returns:
        ConnectionManager: The global connection manager
    """
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
    return _connection_manager


@router.websocket("/screening/{screening_id}")
async def screening_websocket(
    websocket: WebSocket,
    screening_id: str,
    candidate_id: Optional[str] = None,
):
    """WebSocket endpoint for real-time screening progress updates.
    
    This endpoint allows clients to subscribe to real-time updates
    for a specific screening session. Clients receive progress updates,
    new questions, and assessment results as they happen.
    
    Args:
        websocket: The WebSocket connection
        screening_id: The screening session ID to subscribe to
        candidate_id: Optional candidate ID for additional validation
        
    Protocol:
        - Client connects to /ws/screening/{screening_id}
        - Server accepts connection
        - Client receives real-time updates as JSON messages
        - Client can send acknowledgment or heartbeat messages
        - Connection stays open until screening completes or client disconnects
        
    Message Types (server -> client):
        - "progress": General progress update
        - "question": New question available
        - "assessment": Answer assessed
        - "complete": Screening completed
        - "error": Error occurred
        - "heartbeat": Keepalive message
        
    Example message:
        {
            "message_type": "question",
            "screening_id": "screen-123",
            "candidate_id": "cand-456",
            "status": "QUESTION_ASKED",
            "current_question_number": 1,
            "total_questions": 3,
            "progress_percentage": 33.3,
            "current_question": {
                "id": "q1",
                "text": "Explain your experience with...",
                "type": "TECHNICAL_DEPTH",
                "focus_area": "Python",
                "expected_evidence": ["specific examples", "performance metrics"],
                "priority": "REQUIRED"
            },
            "timestamp": "2024-06-28T21:55:00Z"
        }
    """
    manager = get_connection_manager()
    
    # Accept the connection
    connection_id = await manager.connect(websocket)
    
    try:
        logger.info(f"WebSocket connection {connection_id} for screening {screening_id}")
        
        # Subscribe to screening updates
        success = await manager.subscribe(connection_id, screening_id)
        if not success:
            await websocket.send_text(json.dumps({
                "message_type": "error",
                "error": "Failed to subscribe to screening updates",
                "screening_id": screening_id,
            }))
            return
        
        # Send initial confirmation
        await websocket.send_text(json.dumps({
            "message_type": "connected",
            "connection_id": connection_id,
            "screening_id": screening_id,
            "message": "Successfully subscribed to screening updates",
        }))
        
        # Keep connection alive and handle client messages
        while True:
            try:
                # Wait for message from client with timeout
                message = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0,  # 30 second heartbeat timeout
                )
                
                # Parse client message
                try:
                    data = json.loads(message)
                    message_type = data.get("type", "unknown")
                    
                    if message_type == "heartbeat":
                        # Respond to heartbeat
                        await websocket.send_text(json.dumps({
                            "message_type": "heartbeat",
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                        }))
                    
                    elif message_type == "ack":
                        # Acknowledge receipt of a message
                        logger.debug(f"Client acknowledged message: {data.get('message_id')}")
                    
                    else:
                        logger.warning(f"Unknown message type from client: {message_type}")
                        
                except json.JSONDecodeError:
                    logger.warning(f"Received invalid JSON from client: {message}")
                    
            except asyncio.TimeoutError:
                # Send heartbeat to keep connection alive
                try:
                    await websocket.send_text(json.dumps({
                        "message_type": "heartbeat",
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                    }))
                except Exception:
                    # Connection likely closed
                    break
                    
    except WebSocketDisconnect:
        logger.info(f"WebSocket {connection_id} disconnected normally")
        
    except Exception as e:
        logger.exception(f"WebSocket error for {connection_id}: {e}")
        
    finally:
        # Clean up connection
        await manager.disconnect(connection_id)
        logger.info(f"WebSocket connection {connection_id} cleaned up")


@router.websocket("/test")
async def test_websocket(websocket: WebSocket):
    """Simple test endpoint for WebSocket connectivity.
    
    This endpoint can be used to test WebSocket connectivity
    without needing a valid screening_id.
    """
    await websocket.accept()
    
    try:
        await websocket.send_text(json.dumps({
            "message_type": "connected",
            "message": "WebSocket test connection successful",
        }))
        
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            
            await websocket.send_text(json.dumps({
                "message_type": "echo",
                "received": data,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }))
            
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Test WebSocket error: {e}")


def get_router() -> APIRouter:
    """Get the WebSocket router.
    
    Returns:
        APIRouter with WebSocket routes
    """
    return router
