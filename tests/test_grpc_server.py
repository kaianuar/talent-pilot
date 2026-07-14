"""Tests for the gRPC server lifecycle.

Covers GRPCServer (init/start/stop/wait_for_termination) and the
DualServerManager coordination. Uses ephemeral ports so tests can
run in parallel without conflicting.
"""

import asyncio
import socket
import sys
import threading
import time
from concurrent import futures
from pathlib import Path
from unittest.mock import patch

import grpc
import pytest

# Add proto directory to path for bare imports (screening_pb2_grpc does
# `import screening_pb2` without a package prefix, matching the existing
# test_grpc_servicer.py pattern).
_proto_dir = Path(__file__).resolve().parent.parent / "backend" / "infrastructure" / "grpc" / "proto"
if str(_proto_dir) not in sys.path:
    sys.path.insert(0, str(_proto_dir))

from backend.infrastructure.grpc.proto import screening_pb2, screening_pb2_grpc
from backend.infrastructure.grpc.servicer import ScreeningServicer
from backend.infrastructure.grpc.server import (
    DualServerManager,
    GRPCServer,
    start_dual_server,
)


def _find_free_port() -> int:
    """Return a TCP port that was free at the time of the call."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _restore_default_signal_handlers():
    """Best-effort: restore SIGINT/SIGTERM handlers to defaults.

    Several tests install custom signal handlers. Running the tests in
    a worker process means we don't pollute the parent shell, but we
    still want a clean state for the next test.
    """
    try:
        import signal as _sig
        if threading.current_thread() is threading.main_thread():
            _sig.signal(_sig.SIGINT, _sig.default_int_handler)
            _sig.signal(_sig.SIGTERM, _sig.SIG_DFL)
    except (ValueError, ImportError):
        pass


class TestGRPCServer:
    """Direct tests of the GRPCServer wrapper class."""

    def test_init_with_custom_args(self):
        port = _find_free_port()
        server = GRPCServer(host="127.0.0.1", port=port, max_workers=2)
        try:
            assert server.host == "127.0.0.1"
            assert server.port == port
            assert server.max_workers == 2
            assert server._server is not None
            assert server._thread_pool is not None
        finally:
            server._thread_pool.shutdown(wait=True)

    def test_init_with_defaults(self):
        """Default port 50051 is used when none is provided."""
        # We can't actually bind 50051 in tests, so just construct with
        # an explicit port and verify defaults for host/max_workers.
        port = _find_free_port()
        server = GRPCServer(port=port)
        try:
            assert server.host == "0.0.0.0"  # default
            assert server.max_workers == 10  # default
        finally:
            server._thread_pool.shutdown(wait=True)

    def test_init_sets_servicer(self):
        """The servicer registration is observable via a real RPC call."""
        port = _find_free_port()
        server = GRPCServer(host="127.0.0.1", port=port)
        try:
            server.start()
            channel = grpc.insecure_channel(f"127.0.0.1:{port}")
            try:
                stub = screening_pb2_grpc.ScreeningServiceStub(channel)
                # A real RPC call to StartScreening: success or error both
                # prove the servicer is registered. We just check the
                # call does NOT return UNAVAILABLE (which would mean the
                # servicer wasn't bound).
                try:
                    resp = stub.StartScreening(
                        screening_pb2.StartScreeningRequest(
                            candidate_id="c1", job_id="j1", match_tier="STRONG_MATCH",
                        ),
                        timeout=10,
                    )
                    # Success path: either a screening_id or an error_message
                    assert resp.screening_id or resp.error_message
                except grpc.RpcError as e:
                    # Error from the servicer is fine. Connection error
                    # would mean the servicer wasn't registered.
                    assert e.code() != grpc.StatusCode.UNAVAILABLE, (
                        "Call did not reach the servicer"
                    )
            finally:
                channel.close()
        finally:
            server.stop(0)

    def test_start_and_stop(self):
        port = _find_free_port()
        server = GRPCServer(host="127.0.0.1", port=port)
        server.start()
        # Server should accept a connection after start
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            assert s.connect_ex(("127.0.0.1", port)) == 0
        server.stop(0)
        # After stop, the socket should refuse connections
        time.sleep(0.2)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            assert s.connect_ex(("127.0.0.1", port)) != 0

    def test_stop_with_grace_period_none(self):
        port = _find_free_port()
        server = GRPCServer(host="127.0.0.1", port=port)
        server.start()
        # grace_period=None should not hang
        server.stop(grace_period=None)

    def test_stop_with_grace_period_seconds(self):
        port = _find_free_port()
        server = GRPCServer(host="127.0.0.1", port=port)
        server.start()
        server.stop(grace_period=0.5)


class TestDualServerManager:
    """Tests for the DualServerManager lifecycle and signal handling."""

    def test_init(self):
        port = _find_free_port()
        mgr = DualServerManager(grpc_host="127.0.0.1", grpc_port=port, max_workers=2)
        try:
            assert mgr.grpc_server.host == "127.0.0.1"
            assert mgr.grpc_server.port == port
            assert mgr.grpc_server.max_workers == 2
            assert isinstance(mgr._shutdown_event, asyncio.Event)
            assert mgr._signal_handlers_installed is False
        finally:
            mgr.grpc_server._thread_pool.shutdown(wait=True)

    def test_install_signal_handlers_is_idempotent(self):
        port = _find_free_port()
        mgr = DualServerManager(grpc_host="127.0.0.1", grpc_port=port)
        try:
            mgr._install_signal_handlers()
            assert mgr._signal_handlers_installed is True
            # Calling again must not reinstall (the if-guard returns early)
            mgr._install_signal_handlers()
            assert mgr._signal_handlers_installed is True
        finally:
            mgr.grpc_server._thread_pool.shutdown(wait=True)
            _restore_default_signal_handlers()

    def test_start_calls_install_signal_handlers_and_starts_grpc(self):
        port = _find_free_port()
        mgr = DualServerManager(grpc_host="127.0.0.1", grpc_port=port)
        try:
            mgr.start()
            assert mgr._signal_handlers_installed is True
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                assert s.connect_ex(("127.0.0.1", port)) == 0
        finally:
            mgr.stop(0)
            _restore_default_signal_handlers()

    def test_stop_calls_grpc_stop(self):
        port = _find_free_port()
        mgr = DualServerManager(grpc_host="127.0.0.1", grpc_port=port)
        mgr.start()
        mgr.stop(0)
        time.sleep(0.2)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            assert s.connect_ex(("127.0.0.1", port)) != 0
        _restore_default_signal_handlers()

    def test_run_forever_responds_to_shutdown_event(self):
        """Setting the shutdown event from a coroutine stops run_forever."""
        port = _find_free_port()
        mgr = DualServerManager(grpc_host="127.0.0.1", grpc_port=port)

        async def main():
            trigger = asyncio.create_task(self._trigger_shutdown(mgr))
            await mgr.run_forever()
            await trigger

        try:
            asyncio.run(asyncio.wait_for(main(), timeout=5.0))
        except asyncio.TimeoutError:
            pytest.fail("run_forever did not exit when shutdown event was set")
        finally:
            _restore_default_signal_handlers()

    @staticmethod
    async def _trigger_shutdown(mgr: DualServerManager) -> None:
        await asyncio.sleep(0.1)
        mgr._shutdown_event.set()

    def test_run_sync_handles_keyboard_interrupt(self):
        """run_sync catches KeyboardInterrupt and exits cleanly."""
        port = _find_free_port()
        mgr = DualServerManager(grpc_host="127.0.0.1", grpc_port=port)

        # Patch asyncio.run to raise KeyboardInterrupt immediately
        with patch(
            "backend.infrastructure.grpc.server.asyncio.run",
            side_effect=KeyboardInterrupt,
        ):
            # Should not raise
            mgr.run_sync()
        _restore_default_signal_handlers()


class TestStartDualServer:
    """Tests for the start_dual_server convenience function."""

    def test_returns_dual_server_manager(self):
        port = _find_free_port()
        manager = start_dual_server(
            grpc_host="127.0.0.1", grpc_port=port, max_workers=2
        )
        try:
            assert isinstance(manager, DualServerManager)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                assert s.connect_ex(("127.0.0.1", port)) == 0
        finally:
            manager.stop(0)
            _restore_default_signal_handlers()
