"""FastAPI integration for gRPC and WebSocket support.

This module provides the integration layer between FastAPI, gRPC, and WebSocket,
enabling all three protocols to work together seamlessly.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional, AsyncIterator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, APIRouter
from fastapi.middleware.cors import CORSMiddleware

from backend.infrastructure.grpc.server import GRPCServer
from backend.infrastructure.grpc.servicer import ScreeningServicer
from backend.infrastructure.grpc.web_proxy import create_grpc_web_proxy
from backend.infrastructure.websocket.manager import ConnectionManager, ScreeningProgressMessage
from backend.infrastructure.websocket.routes import router as websocket_router


logger = logging.getLogger(__name__)


class FastAPIGRPCIntegration:
    """Integration class for FastAPI, gRPC, and WebSocket.
    
    This class manages the lifecycle of all three protocols,
    ensuring they start and stop together properly.
    """
    
    def __init__(
        self,
        grpc_host: str = "0.0.0.0",
        grpc_port: int = 50051,
        grpc_web_enabled: bool = True,
        websocket_enabled: bool = True,
    ):
        """Initialize the integration.
        
        Args:
            grpc_host: Host for gRPC server
            grpc_port: Port for gRPC server
            grpc_web_enabled: Whether to enable gRPC-Web proxy
            websocket_enabled: Whether to enable WebSocket support
        """
        self.grpc_host = grpc_host
        self.grpc_port = grpc_port
        self.grpc_web_enabled = grpc_web_enabled
        self.websocket_enabled = websocket_enabled
        
        # gRPC server
        self._grpc_server: Optional[GRPCServer] = None
        
        # gRPC-Web proxy
        self._grpc_web_proxy = None
        
        logger.info(
            f"FastAPIGRPCIntegration initialized: "
            f"gRPC={grpc_host}:{grpc_port}, "
            f"gRPC-Web={grpc_web_enabled}, "
            f"WebSocket={websocket_enabled}"
        )
    
    def setup_app(self, app: FastAPI) -> None:
        """Set up FastAPI app with gRPC and WebSocket support.
        
        Args:
            app: The FastAPI application
        """
        # Store reference to integration for lifespan
        app.state.grpc_integration = self
        
        # Add CORS for gRPC-Web
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["grpc-status", "grpc-message"],
        )
        
        # Add WebSocket routes
        if self.websocket_enabled:
            app.include_router(websocket_router)
            logger.info("WebSocket routes added to FastAPI")
        
        # Add gRPC-Web routes
        if self.grpc_web_enabled:
            self._setup_grpc_web_routes(app)
        
        # Set up lifespan
        self._setup_lifespan(app)
        
        logger.info("FastAPI app set up with gRPC and WebSocket support")
    
    def _setup_grpc_web_routes(self, app: FastAPI) -> None:
        """Set up gRPC-Web proxy routes.
        
        Args:
            app: The FastAPI application
        """
        self._grpc_web_proxy = create_grpc_web_proxy(
            grpc_target=f"{self.grpc_host}:{self.grpc_port}",
        )
        
        # Include gRPC-Web routes
        app.include_router(self._grpc_web_proxy.router)
        
        logger.info("gRPC-Web routes added to FastAPI")
    
    def _setup_lifespan(self, app: FastAPI) -> None:
        """Set up application lifespan events.
        
        Args:
            app: The FastAPI application
        """
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            """Application lifespan manager."""
            # Startup
            logger.info("Starting up gRPC and WebSocket servers...")
            await self.startup()
            
            yield
            
            # Shutdown
            logger.info("Shutting down gRPC and WebSocket servers...")
            await self.shutdown()
        
        # Replace the app's lifespan
        app.router.lifespan_context = lifespan
    
    async def startup(self) -> None:
        """Start all servers."""
        # Start gRPC server
        self._grpc_server = GRPCServer(
            host=self.grpc_host,
            port=self.grpc_port,
        )
        self._grpc_server.start()
        
        logger.info("All servers started successfully")
    
    async def shutdown(self) -> None:
        """Stop all servers."""
        # Stop gRPC server
        if self._grpc_server:
            self._grpc_server.stop(grace_period=30.0)
        
        # Stop gRPC-Web proxy
        if self._grpc_web_proxy:
            await self._grpc_web_proxy.close()
        
        logger.info("All servers stopped")


def create_integrated_app(
    grpc_host: str = "0.0.0.0",
    grpc_port: int = 50051,
    grpc_web_enabled: bool = True,
    websocket_enabled: bool = True,
) -> tuple[FastAPI, FastAPIGRPCIntegration]:
    """Create a FastAPI app with full gRPC and WebSocket integration.
    
    This is a convenience function that creates and configures a FastAPI
    application with all the gRPC and WebSocket components properly set up.
    
    Args:
        grpc_host: Host for gRPC server
        grpc_port: Port for gRPC server
        grpc_web_enabled: Whether to enable gRPC-Web proxy
        websocket_enabled: Whether to enable WebSocket support
        
    Returns:
        Tuple of (FastAPI app, integration manager)
    """
    from fastapi import FastAPI
    
    # Create FastAPI app
    app = FastAPI(
        title="TalentPilot API",
        description="AI-powered recruitment screening API with gRPC and WebSocket support",
        version="2.0.0",
    )
    
    # Create integration manager
    integration = FastAPIGRPCIntegration(
        grpc_host=grpc_host,
        grpc_port=grpc_port,
        grpc_web_enabled=grpc_web_enabled,
        websocket_enabled=websocket_enabled,
    )
    
    # Set up the app
    integration.setup_app(app)
    
    return app, integration
