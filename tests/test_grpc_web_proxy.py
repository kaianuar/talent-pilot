"""Tests for gRPC-Web proxy — frame encoding/decoding, trailer generation,
method routing, channel readiness, error handling, and health check."""

import asyncio
import struct
import sys
from pathlib import Path
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import grpc
from fastapi import HTTPException

# Proto file has bare `import screening_pb2`; add proto dir to sys.path
_proto_dir = Path(__file__).resolve().parent.parent / "backend" / "infrastructure" / "grpc" / "proto"
if str(_proto_dir) not in sys.path:
    sys.path.insert(0, str(_proto_dir))

from backend.infrastructure.grpc.web_proxy import GRPCWebProxy, GRPC_TIMEOUT


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _encode_grpc_web_frame(payload: bytes, flag: int = 0) -> bytes:
    """Encode a payload into gRPC-Web binary frame (5-byte header)."""
    return bytes([flag]) + len(payload).to_bytes(4, "big") + payload


def _make_proxy() -> GRPCWebProxy:
    """Create a GRPCWebProxy with mocked channel/stub for unit tests."""
    with patch("grpc.insecure_channel"):
        proxy = GRPCWebProxy(grpc_target="localhost:9999")
    return proxy


def _mock_request(body: bytes):
    """Create a mock FastAPI Request with given body."""
    req = MagicMock()
    req.body = AsyncMock(return_value=body)
    return req


class _FakeRpcError(grpc.RpcError, Exception):
    """Fake gRPC error that passes `except grpc.RpcError` checks."""

    def __init__(self, code: grpc.StatusCode, details: str = ""):
        self._code = code
        self._details = details

    def code(self):
        return self._code

    def details(self):
        return self._details


def _make_grpc_error(code=grpc.StatusCode.INTERNAL, details="something broke"):
    """Create a fake gRPC RpcError with the given status code and details."""
    return _FakeRpcError(code=code, details=details)


# ---------------------------------------------------------------------------
# Init / properties
# ---------------------------------------------------------------------------

class TestGRPCWebProxyInit:

    def test_default_target(self):
        with patch("grpc.insecure_channel"):
            proxy = GRPCWebProxy()
            assert proxy.grpc_target == "localhost:50051"

    def test_custom_target(self):
        with patch("grpc.insecure_channel"):
            proxy = GRPCWebProxy(grpc_target="10.0.0.1:50052")
            assert proxy.grpc_target == "10.0.0.1:50052"

    def test_router_prefix(self):
        proxy = _make_proxy()
        assert proxy.router.prefix == "/grpc-web"

    def test_channel_lazy(self):
        """Channel is not created until first access."""
        proxy = _make_proxy()
        assert proxy._channel is None

    def test_channel_creates_on_access(self):
        with patch("grpc.insecure_channel") as mock_ch:
            mock_ch.return_value = MagicMock()
            proxy = GRPCWebProxy(grpc_target="localhost:9999")
            ch = proxy.channel
            mock_ch.assert_called_once_with("localhost:9999")
            assert ch is proxy._channel

    def test_stub_lazy(self):
        proxy = _make_proxy()
        assert proxy._stub is None

    def test_stub_creates_on_access(self):
        with patch("backend.infrastructure.grpc.web_proxy.screening_pb2_grpc.ScreeningServiceStub") as MockStub:
            mock_stub_instance = MagicMock()
            MockStub.return_value = mock_stub_instance
            with patch("grpc.insecure_channel") as mock_ch:
                mock_ch.return_value = MagicMock()
                proxy = GRPCWebProxy(grpc_target="localhost:9999")
                s = proxy.stub
                MockStub.assert_called_once()
                assert s is mock_stub_instance


# ---------------------------------------------------------------------------
# _ensure_channel_ready
# ---------------------------------------------------------------------------

class TestEnsureChannelReady:

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_success(self):
        proxy = _make_proxy()
        mock_future = MagicMock()
        mock_future.result.return_value = None

        with patch("backend.infrastructure.grpc.web_proxy.grpc.channel_ready_future", return_value=mock_future):
            await proxy._ensure_channel_ready()
            mock_future.result.assert_called_once_with(timeout=5)

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_timeout_raises_503(self):
        proxy = _make_proxy()
        mock_future = MagicMock()
        mock_future.result.side_effect = grpc.FutureTimeoutError()

        with patch("backend.infrastructure.grpc.web_proxy.grpc.channel_ready_future", return_value=mock_future):
            with pytest.raises(HTTPException) as exc_info:
                await proxy._ensure_channel_ready()
            assert exc_info.value.status_code == 503

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_other_exception_is_warning(self):
        """Non-timeout exceptions are logged but not raised."""
        proxy = _make_proxy()
        mock_future = MagicMock()
        mock_future.result.side_effect = RuntimeError("unexpected")

        with patch("backend.infrastructure.grpc.web_proxy.grpc.channel_ready_future", return_value=mock_future):
            # Should not raise — just logs warning
            await proxy._ensure_channel_ready()


# ---------------------------------------------------------------------------
# Frame encoding / decoding
# ---------------------------------------------------------------------------

class TestFrameEncoding:

    def test_encode_decode_roundtrip(self):
        """Encode a payload and verify the 5-byte header structure."""
        payload = b"hello grpc"
        frame = _encode_grpc_web_frame(payload)
        assert frame[0] == 0  # flag byte
        msg_len = int.from_bytes(frame[1:5], "big")
        assert msg_len == len(payload)
        assert frame[5:] == payload

    def test_trailer_frame_flag(self):
        """Trailer frames use flag 0x80."""
        trailer = b"grpc-status: 0\r\n"
        frame = _encode_grpc_web_frame(trailer, flag=0x80)
        assert frame[0] == 0x80

    def test_empty_payload(self):
        frame = _encode_grpc_web_frame(b"")
        assert len(frame) == 5
        assert int.from_bytes(frame[1:5], "big") == 0


# ---------------------------------------------------------------------------
# Trailer frame generation
# ---------------------------------------------------------------------------

class TestTrailerFrameGeneration:

    def test_success_trailer_format(self):
        """Verify the success trailer bytes format."""
        trailer_bytes = b"grpc-status: 0\r\ngrpc-message: \r\n"
        trailer_frame = (
            bytes([0x80])
            + len(trailer_bytes).to_bytes(4, "big")
            + trailer_bytes
        )
        assert trailer_frame[0] == 0x80
        length = int.from_bytes(trailer_frame[1:5], "big")
        assert length == len(trailer_bytes)
        content = trailer_frame[5:].decode()
        assert "grpc-status: 0" in content

    def test_error_trailer_format(self):
        """Verify error trailer encoding for gRPC errors."""
        error_status = "13"
        error_trailer = (
            f"grpc-status: {error_status}\r\n"
            f"grpc-message: internal error\r\n"
        ).encode()
        trailer_frame = (
            bytes([0x80])
            + len(error_trailer).to_bytes(4, "big")
            + error_trailer
        )
        assert trailer_frame[0] == 0x80
        content = trailer_frame[5:].decode()
        assert "grpc-status: 13" in content
        assert "grpc-message: internal error" in content


# ---------------------------------------------------------------------------
# Method routing — proxy_grpc_web
# ---------------------------------------------------------------------------

class TestProxyGRPCWebMethodRouting:
    """Test each method routes to the correct stub call."""

    @pytest.fixture(autouse=True)
    def setup_proxy(self):
        self.proxy = _make_proxy()
        self.mock_stub = MagicMock()
        self.proxy._stub = self.mock_stub

    async def _call_proxy(self, method: str, payload: bytes = b""):
        """Find the registered route handler and call it."""
        for route in self.proxy.router.routes:
            if hasattr(route, "path") and "{method}" in route.path:
                endpoint = route.endpoint
                req = _mock_request(_encode_grpc_web_frame(payload))
                with patch.object(self.proxy, "_ensure_channel_ready", new_callable=AsyncMock):
                    return await endpoint(method=method, request=req)
        pytest.fail("Route not found")

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_start_screening(self):
        mock_resp = MagicMock()
        mock_resp.SerializeToString.return_value = b"\x08\x01"
        self.mock_stub.StartScreening.return_value = mock_resp

        resp = await self._call_proxy("StartScreening")
        assert resp.status_code == 200
        self.mock_stub.StartScreening.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_get_next_question(self):
        mock_resp = MagicMock()
        mock_resp.SerializeToString.return_value = b"\x08\x02"
        self.mock_stub.GetNextQuestion.return_value = mock_resp

        resp = await self._call_proxy("GetNextQuestion")
        assert resp.status_code == 200
        self.mock_stub.GetNextQuestion.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_submit_answer(self):
        mock_resp = MagicMock()
        mock_resp.SerializeToString.return_value = b"\x08\x03"
        self.mock_stub.SubmitAnswer.return_value = mock_resp

        resp = await self._call_proxy("SubmitAnswer")
        assert resp.status_code == 200
        self.mock_stub.SubmitAnswer.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_get_screening_result(self):
        mock_resp = MagicMock()
        mock_resp.SerializeToString.return_value = b"\x08\x04"
        self.mock_stub.GetScreeningResult.return_value = mock_resp

        resp = await self._call_proxy("GetScreeningResult")
        assert resp.status_code == 200
        self.mock_stub.GetScreeningResult.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_unknown_method_returns_error(self):
        """Unknown method raises HTTPException (wrapped as 500 by outer handler)."""
        with pytest.raises(HTTPException) as exc_info:
            await self._call_proxy("BogusMethod")
        # The outer except Exception handler wraps it as 500
        assert exc_info.value.status_code == 500
        assert "Unknown method" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_invalid_frame_too_short(self):
        """Body shorter than 5 bytes → HTTPException (wrapped as 500 by outer handler)."""
        for route in self.proxy.router.routes:
            if hasattr(route, "path") and "{method}" in route.path:
                endpoint = route.endpoint
                req = _mock_request(b"\x00\x01")  # only 2 bytes
                with pytest.raises(HTTPException) as exc_info:
                    await endpoint(method="StartScreening", request=req)
                # The outer except Exception handler wraps it as 500
                assert exc_info.value.status_code == 500
                assert "Invalid gRPC-Web frame" in str(exc_info.value.detail)
                return
        pytest.fail("Route not found")

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_response_content_type(self):
        """Successful response has grpc-web+proto content type."""
        mock_resp = MagicMock()
        mock_resp.SerializeToString.return_value = b"\x08\x01"
        self.mock_stub.StartScreening.return_value = mock_resp

        resp = await self._call_proxy("StartScreening")
        assert resp.headers["Content-Type"] == "application/grpc-web+proto"

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_response_contains_message_and_trailer(self):
        """Response body = message frame + trailer frame."""
        payload_bytes = b"\x08\x01\x10\x02"
        mock_resp = MagicMock()
        mock_resp.SerializeToString.return_value = payload_bytes
        self.mock_stub.StartScreening.return_value = mock_resp

        resp = await self._call_proxy("StartScreening")
        body = resp.body
        # Message frame: flag=0, 4-byte length, payload
        assert body[0] == 0
        msg_len = int.from_bytes(body[1:5], "big")
        assert msg_len == len(payload_bytes)
        assert body[5:5 + msg_len] == payload_bytes

        # Trailer frame starts right after
        trailer_start = 5 + msg_len
        assert body[trailer_start] == 0x80
        trailer_len = int.from_bytes(body[trailer_start + 1:trailer_start + 5], "big")
        trailer_content = body[trailer_start + 5:trailer_start + 5 + trailer_len].decode()
        assert "grpc-status: 0" in trailer_content


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestProxyErrorHandling:

    @pytest.fixture(autouse=True)
    def setup_proxy(self):
        self.proxy = _make_proxy()
        self.mock_stub = MagicMock()
        self.proxy._stub = self.mock_stub

    async def _call_proxy(self, method: str, payload: bytes = b""):
        for route in self.proxy.router.routes:
            if hasattr(route, "path") and "{method}" in route.path:
                endpoint = route.endpoint
                req = _mock_request(_encode_grpc_web_frame(payload))
                with patch.object(self.proxy, "_ensure_channel_ready", new_callable=AsyncMock):
                    return await endpoint(method=method, request=req)
        pytest.fail("Route not found")

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_grpc_error_returns_trailer(self):
        """gRPC RpcError → 200 response with error trailer frame."""
        grpc_err = _make_grpc_error(
            code=grpc.StatusCode.NOT_FOUND,
            details="screening not found",
        )
        self.mock_stub.StartScreening.side_effect = grpc_err

        resp = await self._call_proxy("StartScreening")
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == "application/grpc-web+proto"

        body = resp.body
        assert body[0] == 0x80  # trailer flag
        trailer_len = int.from_bytes(body[1:5], "big")
        trailer_content = body[5:5 + trailer_len].decode()
        assert "grpc-status:" in trailer_content
        assert "screening not found" in trailer_content

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_generic_exception_raises_500(self):
        """Non-gRPC exception → HTTPException 500."""
        self.mock_stub.StartScreening.side_effect = RuntimeError("oops")

        for route in self.proxy.router.routes:
            if hasattr(route, "path") and "{method}" in route.path:
                endpoint = route.endpoint
                req = _mock_request(_encode_grpc_web_frame(b""))
                with patch.object(self.proxy, "_ensure_channel_ready", new_callable=AsyncMock):
                    with pytest.raises(HTTPException) as exc_info:
                        await endpoint(method="StartScreening", request=req)
                    assert exc_info.value.status_code == 500
                    return
        pytest.fail("Route not found")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestHealthCheck:

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_health_returns_ok(self):
        proxy = _make_proxy()
        for route in proxy.router.routes:
            if hasattr(route, "path") and "health" in route.path:
                endpoint = route.endpoint
                result = await endpoint()
                assert result["status"] == "healthy"
                assert result["grpc_target"] == "localhost:9999"
                assert "timestamp" in result
                return
        pytest.fail("Health route not found")


# ---------------------------------------------------------------------------
# close()
# ---------------------------------------------------------------------------

class TestClose:

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_close_with_channel(self):
        proxy = _make_proxy()
        mock_channel = MagicMock()
        proxy._channel = mock_channel
        proxy._stub = MagicMock()

        await proxy.close()
        mock_channel.close.assert_called_once()
        assert proxy._channel is None
        assert proxy._stub is None

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_close_without_channel(self):
        proxy = _make_proxy()
        assert proxy._channel is None
        await proxy.close()  # no-op, no exception

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_close_idempotent(self):
        proxy = _make_proxy()
        mock_channel = MagicMock()
        proxy._channel = mock_channel
        await proxy.close()
        await proxy.close()  # second call is a no-op


# ---------------------------------------------------------------------------
# GRPC_TIMEOUT constant
# ---------------------------------------------------------------------------

class TestConstants:
    def test_grpc_timeout(self):
        assert GRPC_TIMEOUT == 30
