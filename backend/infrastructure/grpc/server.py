"""gRPC server integration for FastAPI.

This module provides the gRPC server that runs alongside the FastAPI HTTP server,
enabling both REST and gRPC endpoints for the screening service.
"""

import asyncio
import logging
import signal
from concurrent import futures
from typing import Optional

import grpc

from backend.infrastructure.grpc.proto import screening_pb2_grpc
from backend.infrastructure.grpc.servicer import ScreeningServicer


logger = logging.getLogger(__name__)


class GRPCServer:
    """gRPC server for the screening service.
    
    This server runs in a separate thread and handles gRPC requests
    while the main FastAPI server handles HTTP requests.
    """
    
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 50051,
        max_workers: int = 10,
    ):
        """Initialize the gRPC server.
        
        Args:
            host: Host address to bind to
            port: Port to listen on
            max_workers: Maximum number of worker threads
        """
        self.host = host
        self.port = port
        self.max_workers = max_workers
        
        # Create thread pool for gRPC
        self._thread_pool = futures.ThreadPoolExecutor(max_workers=max_workers)
        
        # Create gRPC server
        self._server = grpc.server(
            self._thread_pool,
            options=[
                ('grpc.max_send_message_length', 50 * 1024 * 1024),  # 50MB
                ('grpc.max_receive_message_length', 50 * 1024 * 1024),  # 50MB
            ],
        )
        
        # Add servicer
        screening_pb2_grpc.add_ScreeningServiceServicer_to_server(
            ScreeningServicer(),
            self._server,
        )
        
        # Bind to address
        address = f"{host}:{port}"
        self._server.add_insecure_port(address)
        
        logger.info(f"gRPC server initialized on {address}")
    
    def start(self) -> None:
        """Start the gRPC server."""
        self._server.start()
        logger.info(f"gRPC server started on {self.host}:{self.port}")
    
    def stop(self, grace_period: Optional[float] = None) -> None:
        """Stop the gRPC server.
        
        Args:
            grace_period: Seconds to wait for graceful shutdown (None = indefinite)
        """
        logger.info("Stopping gRPC server...")
        self._server.stop(grace_period)
        self._thread_pool.shutdown(wait=True)
        logger.info("gRPC server stopped")
    
    def wait_for_termination(self, timeout: Optional[float] = None) -> bool:
        """Wait for the server to terminate.
        
        Args:
            timeout: Maximum seconds to wait (None = indefinite)
            
        Returns:
            True if server terminated, False if timeout
        """
        return self._server.wait_for_termination(timeout)


class DualServerManager:
    """Manager for running both FastAPI HTTP and gRPC servers together.
    
    This manager handles the lifecycle of both servers, including
    graceful shutdown on interrupt signals.
    """
    
    def __init__(
        self,
        grpc_host: str = "0.0.0.0",
        grpc_port: int = 50051,
        max_workers: int = 10,
    ):
        """Initialize the dual server manager.
        
        Args:
            grpc_host: gRPC server host
            grpc_port: gRPC server port
            max_workers: Maximum gRPC worker threads
        """
        self.grpc_server = GRPCServer(
            host=grpc_host,
            port=grpc_port,
            max_workers=max_workers,
        )
        
        self._shutdown_event = asyncio.Event()
        self._signal_handlers_installed = False
        
        logger.info("DualServerManager initialized")
    
    def _install_signal_handlers(self) -> None:
        """Install signal handlers for graceful shutdown."""
        if self._signal_handlers_installed:
            return
        
        def signal_handler(sig, frame):
            logger.info(f"Received signal {sig}, initiating shutdown...")
            self._shutdown_event.set()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        self._signal_handlers_installed = True
        logger.info("Signal handlers installed")
    
    def start(self) -> None:
        """Start both servers."""
        self._install_signal_handlers()
        self.grpc_server.start()
        logger.info("Both servers started (HTTP via FastAPI, gRPC)")
    
    def stop(self, grace_period: Optional[float] = None) -> None:
        """Stop both servers.
        
        Args:
            grace_period: Seconds to wait for graceful shutdown
        """
        logger.info("Stopping both servers...")
        self.grpc_server.stop(grace_period)
        logger.info("Both servers stopped")
    
    async def run_forever(self) -> None:
        """Run both servers until shutdown signal is received."""
        self.start()
        
        try:
            await self._shutdown_event.wait()
        except asyncio.CancelledError:
            logger.info("Run cancelled, shutting down...")
        finally:
            self.stop(grace_period=30.0)
    
    def run_sync(self) -> None:
        """Run both servers synchronously until interrupted."""
        try:
            asyncio.run(self.run_forever())
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received, exiting...")


# Convenience function for starting the dual server
def start_dual_server(
    grpc_host: str = "0.0.0.0",
    grpc_port: int = 50051,
    max_workers: int = 10,
) -> DualServerManager:
    """Create and start both HTTP and gRPC servers.
    
    Args:
        grpc_host: gRPC server host
        grpc_port: gRPC server port
        max_workers: Maximum gRPC worker threads
        
    Returns:
        DualServerManager instance
    """
    manager = DualServerManager(
        grpc_host=grpc_host,
        grpc_port=grpc_port,
        max_workers=max_workers,
    )
    manager.start()
    return manager
