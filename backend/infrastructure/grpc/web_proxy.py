"""gRPC-Web proxy for browser support.

Translates gRPC-Web HTTP/1.1 requests from the browser into native gRPC
calls to the screening service using grpc's insecure channel (h2c).
"""
from datetime import datetime, timezone
import logging
from typing import Any

from fastapi import APIRouter, Request, Response, HTTPException
import grpc

from backend.infrastructure.grpc.proto import screening_pb2, screening_pb2_grpc

logger = logging.getLogger(__name__)

# Maps gRPC method names to their handler functions
METHOD_MAP: dict[str, Any] = {}


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

    def _register_routes(self) -> None:
        """Register FastAPI routes for gRPC-Web proxy."""

        @self.router.post("/talentpilot.screening.ScreeningService/{method}")
        async def proxy_grpc_web(method: str, request: Request) -> Response:
            """Proxy a gRPC-Web request to the gRPC ScreeningService."""
            try:
                body = await request.body()

                # Parse the gRPC-Web frame (5-byte header: 1 flag + 4 length)
                if len(body) < 5:
                    raise HTTPException(400, "Invalid gRPC-Web frame: too short")

                flag = body[0]
                msg_len = int.from_bytes(body[1:5], "big")
                payload = body[5 : 5 + msg_len]

                # Route to the appropriate RPC method
                if method == "StartScreening":
                    req = screening_pb2.StartScreeningRequest()
                    req.ParseFromString(payload)
                    resp = self.stub.StartScreening(req)
                elif method == "GetNextQuestion":
                    req = screening_pb2.GetNextQuestionRequest()
                    req.ParseFromString(payload)
                    resp = self.stub.GetNextQuestion(req)
                elif method == "SubmitAnswer":
                    req = screening_pb2.SubmitAnswerRequest()
                    req.ParseFromString(payload)
                    resp = self.stub.SubmitAnswer(req)
                elif method == "GetScreeningResult":
                    req = screening_pb2.GetScreeningResultRequest()
                    req.ParseFromString(payload)
                    resp = self.stub.GetScreeningResult(req)
                else:
                    raise HTTPException(404, f"Unknown gRPC method: {method}")

                # Encode response as gRPC-Web frame
                resp_bytes = resp.SerializeToString()
                frame = bytes([0]) + len(resp_bytes).to_bytes(4, "big") + resp_bytes

                return Response(
                    content=frame,
                    status_code=200,
                    headers={"Content-Type": "application/grpc-web+proto"},
                )

            except grpc.RpcError as e:
                logger.error(f"gRPC error calling {method}: {e.code()} — {e.details()}")
                raise HTTPException(502, f"gRPC error: {e.details()}")
            except Exception as e:
                logger.exception(f"Error proxying gRPC-Web request: {e}")
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
