"""gRPC-Web proxy for browser support.

gRPC-Web is a protocol that allows gRPC to be used from browser-based clients
using HTTP/1.1. This proxy translates between gRPC-Web requests and gRPC
requests, allowing the same gRPC service to serve both native and web clients.

Reference: https://github.com/grpc/grpc-web
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, Callable, Awaitable
from dataclasses import dataclass
from enum import Enum

from fastapi import APIRouter, Request, Response, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
import httpx


logger = logging.getLogger(__name__)


class GRPCWebContentType(str, Enum):
    """gRPC-Web content types."""
    PROTO = "application/grpc-web"
    PROTO_TEXT = "application/grpc-web-text"
    JSON = "application/grpc-web+json"


@dataclass
class GRPCWebFrame:
    """A gRPC-Web frame.
    
    gRPC-Web uses a framing protocol where messages are wrapped in frames:
    - 1 byte: flags (compressed, etc.)
    - 4 bytes: message length (big-endian)
    - N bytes: message data (protobuf or JSON)
    """
    flags: int
    message: bytes
    
    @classmethod
    def from_bytes(cls, data: bytes) -> "GRPCWebFrame":
        """Parse a frame from bytes."""
        if len(data) < 5:
            raise ValueError(f"Frame too short: {len(data)} bytes")
        
        flags = data[0]
        length = int.from_bytes(data[1:5], byteorder="big")
        message = data[5:5+length]
        
        return cls(flags=flags, message=message)
    
    def to_bytes(self) -> bytes:
        """Serialize frame to bytes."""
        length_bytes = len(self.message).to_bytes(4, byteorder="big")
        return bytes([self.flags]) + length_bytes + self.message


class GRPCWebProxy:
    """gRPC-Web proxy for browser clients.
    
    This proxy translates gRPC-Web requests (HTTP/1.1 + binary or JSON framing)
    to gRPC requests (HTTP/2 + protobuf), allowing the same gRPC service to
    serve both native and web clients.
    """
    
    def __init__(
        self,
        grpc_target: str = "localhost:50051",
        timeout: float = 30.0,
    ):
        """Initialize the gRPC-Web proxy.
        
        Args:
            grpc_target: The gRPC server target (host:port)
            timeout: Request timeout in seconds
        """
        self.grpc_target = grpc_target
        self.timeout = timeout
        
        # Create HTTP client for proxying to gRPC server
        self._client = httpx.AsyncClient(
            http2=True,  # Enable HTTP/2 for gRPC
            timeout=httpx.Timeout(timeout),
        )
        
        # Create FastAPI router
        self.router = APIRouter(prefix="/grpc-web", tags=["grpc-web"])
        
        # Register routes
        self._register_routes()
        
        logger.info(f"gRPC-Web proxy initialized, targeting {grpc_target}")
    
    def _register_routes(self) -> None:
        """Register FastAPI routes for gRPC-Web proxy."""
        
        @self.router.post("/{service}/{method}")
        async def proxy_grpc_web(
            service: str,
            method: str,
            request: Request,
            background_tasks: BackgroundTasks,
        ) -> Response:
            """Proxy gRPC-Web request to gRPC server."""
            
            # Read request body
            body = await request.body()
            
            # Determine content type
            content_type = request.headers.get("content-type", "")
            accept = request.headers.get("accept", "")
            
            # Parse gRPC-Web request
            if "grpc-web-text" in content_type or "grpc-web-text" in accept:
                # Base64-encoded framing
                import base64
                try:
                    body = base64.b64decode(body)
                except Exception as e:
                    logger.error(f"Failed to decode base64 gRPC-Web request: {e}")
                    raise HTTPException(400, "Invalid base64 encoding")
            
            # Build gRPC request
            # gRPC uses HTTP/2 with specific headers
            grpc_headers = {
                "Content-Type": "application/grpc",
                "TE": "trailers",
                # Add any custom metadata from the gRPC-Web request
            }
            
            # Copy relevant headers from gRPC-Web request
            for header in ["x-grpc-web", "x-user-agent"]:
                if header in request.headers:
                    grpc_headers[header] = request.headers[header]
            
            # Build gRPC URL
            # gRPC uses the path format: /{package}.{service}/{method}
            # For simplicity, we assume the service name matches
            grpc_url = f"http://{self.grpc_target}/{service}/{method}"
            
            try:
                # Forward request to gRPC server
                grpc_response = await self._client.post(
                    grpc_url,
                    content=body,
                    headers=grpc_headers,
                )
                
                # Read response body
                response_body = grpc_response.content
                
                # Determine response content type
                response_content_type = "application/grpc-web"
                if "grpc-web-text" in accept:
                    # Encode as base64 for text mode
                    import base64
                    response_body = base64.b64encode(response_body)
                    response_content_type = "application/grpc-web-text"
                
                # Build response
                response_headers = dict(grpc_response.headers)
                response_headers["content-type"] = response_content_type
                
                return Response(
                    content=response_body,
                    status_code=grpc_response.status_code,
                    headers=response_headers,
                )
                
            except httpx.TimeoutException:
                logger.error(f"Timeout proxying request to {grpc_url}")
                raise HTTPException(504, "Gateway timeout")
            except httpx.ConnectError as e:
                logger.error(f"Failed to connect to gRPC server at {self.grpc_target}: {e}")
                raise HTTPException(503, "gRPC server unavailable")
            except Exception as e:
                logger.exception(f"Error proxying gRPC request: {e}")
                raise HTTPException(500, f"Proxy error: {str(e)}")
        
        @self.router.get("/health")
        async def health_check() -> dict:
            """Health check endpoint for gRPC-Web proxy."""
            return {
                "status": "healthy",
                "grpc_target": self.grpc_target,
                "timestamp": datetime.utcnow().isoformat(),
            }
    
    async def close(self) -> None:
        """Close the proxy and release resources."""
        await self._client.aclose()
        logger.info("gRPC-Web proxy closed")


def create_grpc_web_proxy(
    grpc_target: str = "localhost:50051",
    timeout: float = 30.0,
) -> GRPCWebProxy:
    """Create a gRPC-Web proxy instance.
    
    Args:
        grpc_target: The gRPC server target (host:port)
        timeout: Request timeout in seconds
        
    Returns:
        GRPCWebProxy instance
    """
    return GRPCWebProxy(
        grpc_target=grpc_target,
        timeout=timeout,
    )
