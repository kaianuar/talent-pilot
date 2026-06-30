"""gRPC-Web proxy for browser support.

Translates gRPC-Web HTTP/1.1 requests from the browser into native gRPC
calls to the screening service using grpc's insecure channel (h2c).
"""
import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Response, HTTPException
import grpc

from backend.infrastructure.grpc.proto import screening_pb2, screening_pb2_grpc

logger = logging.getLogger(__name__)

GRPC_TIMEOUT = 30  # seconds


class GRPCWebProxy:
    """gRPC-Web proxy that bridges browser HTTP/1.1 to native gRPC."""

    def __init__(self, grpc_target: str = "localhost:50051"):
        self.grpc_target = grpc_target
        self._channel: grpc.Channel | None = None
        self._stub: screening_pb2_grpc.ScreeningServiceStub | None = None

        self.router = APIRouter(prefix="/grpc-web", tags=["grpc-web"])
        self._register_routes()
        logger.info(f"gRPC-Web proxy initialized, targeting {grpc_target}")

    @property
    def channel(self) -> grpc.Channel:
        if self._channel is None:
            self._channel = grpc.insecure_channel(self.grpc_target)
        return self._channel

    @property
    def stub(self) -> screening_pb2_grpc.ScreeningServiceStub:
        if self._stub is None:
            self._stub = screening_pb2_grpc.ScreeningServiceStub(self.channel)
        return self._stub

    async def _ensure_channel_ready(self) -> None:
        """Wait for the gRPC channel to be ready."""
        try:
            future = grpc.channel_ready_future(self.channel)
            await asyncio.to_thread(future.result, timeout=5)
        except grpc.FutureTimeoutError:
            raise HTTPException(503, "gRPC server not ready")
        except Exception as e:
            logger.warning(f"Channel ready check failed: {e}")

    def _register_routes(self) -> None:
        """Register FastAPI routes for gRPC-Web proxy."""

        @self.router.post(
            "/talentpilot.screening.ScreeningService/{method}"
        )
        async def proxy_grpc_web(
            method: str, request: Request
        ) -> Response:
            """Proxy a gRPC-Web request to the gRPC ScreeningService."""
            logger.info(f"gRPC-Web proxy: {method} called")
            try:
                body = await request.body()

                # Parse the gRPC-Web frame (5-byte header)
                if len(body) < 5:
                    raise HTTPException(400, "Invalid gRPC-Web frame")

                _flag = body[0]
                msg_len = int.from_bytes(body[1:5], "big")
                payload = body[5 : 5 + msg_len]

                # Ensure channel is ready
                await self._ensure_channel_ready()

                # Route to the appropriate RPC method
                if method == "StartScreening":
                    req = screening_pb2.StartScreeningRequest()
                    req.ParseFromString(payload)
                    resp = await asyncio.to_thread(
                        self.stub.StartScreening, req, timeout=GRPC_TIMEOUT,
                    )
                elif method == "GetNextQuestion":
                    req = screening_pb2.GetNextQuestionRequest()
                    req.ParseFromString(payload)
                    resp = await asyncio.to_thread(
                        self.stub.GetNextQuestion, req, timeout=GRPC_TIMEOUT,
                    )
                elif method == "SubmitAnswer":
                    req = screening_pb2.SubmitAnswerRequest()
                    req.ParseFromString(payload)
                    resp = await asyncio.to_thread(
                        self.stub.SubmitAnswer, req, timeout=GRPC_TIMEOUT,
                    )
                elif method == "GetScreeningResult":
                    req = screening_pb2.GetScreeningResultRequest()
                    req.ParseFromString(payload)
                    resp = await asyncio.to_thread(
                        self.stub.GetScreeningResult, req, timeout=GRPC_TIMEOUT,
                    )
                else:
                    raise HTTPException(404, f"Unknown method: {method}")

                logger.info(f"gRPC-Web proxy: {method} succeeded")

                # Encode response as gRPC-Web frame
                resp_bytes = resp.SerializeToString()
                msg_frame = (
                    bytes([0])
                    + len(resp_bytes).to_bytes(4, "big")
                    + resp_bytes
                )

                # gRPC-Web binary format requires trailer frame in the body
                # (flag=0x80) with gRPC status headers
                trailer_bytes = b"grpc-status: 0\r\ngrpc-message: \r\n"
                trailer_frame = (
                    bytes([0x80])
                    + len(trailer_bytes).to_bytes(4, "big")
                    + trailer_bytes
                )

                return Response(
                    content=msg_frame + trailer_frame,
                    status_code=200,
                    headers={
                        "Content-Type": "application/grpc-web+proto",
                    },
                )

            except grpc.RpcError as e:
                logger.error(
                    f"gRPC error calling {method}: "
                    f"code={e.code()}, details={e.details()}"
                )
                # Return gRPC-Web error with trailer frame
                error_status = str(e.code().value[0])
                error_trailer = (
                    f"grpc-status: {error_status}\r\n"
                    f"grpc-message: {e.details()}\r\n"
                ).encode()
                trailer_frame = (
                    bytes([0x80])
                    + len(error_trailer).to_bytes(4, "big")
                    + error_trailer
                )
                return Response(
                    content=trailer_frame,
                    status_code=200,
                    headers={
                        "Content-Type": "application/grpc-web+proto",
                    },
                )
            except Exception as e:
                logger.exception(
                    f"Error proxying gRPC-Web request: {e}"
                )
                raise HTTPException(500, f"Proxy error: {str(e)}")

        @self.router.get("/health")
        async def health_check() -> dict:
            """Health check endpoint for gRPC-Web proxy."""
            return {
                "status": "healthy",
                "grpc_target": self.grpc_target,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def close(self) -> None:
        """Close the gRPC channel."""
        if self._channel:
            self._channel.close()
            self._channel = None
            self._stub = None
            logger.info("gRPC-Web proxy closed")
