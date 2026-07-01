"""Tests for WebSocket routes — connection handling, message parsing,
heartbeat, disconnect cleanup, and error paths."""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import WebSocket, WebSocketDisconnect

from backend.infrastructure.websocket.manager import (
    ConnectionManager,
    ScreeningProgressMessage,
    QuestionData,
    AssessmentData,
    ScreeningStatus,
)
from backend.infrastructure.websocket import routes as ws_routes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_websocket():
    """Create a mock WebSocket with AsyncMock for send/receive."""
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    ws.receive_text = AsyncMock()
    ws.close = AsyncMock()
    return ws


def _make_progress_msg(screening_id="s1", status="STARTED"):
    return ScreeningProgressMessage(
        message_type="progress",
        screening_id=screening_id,
        candidate_id="c1",
        status=status,
        current_question_number=1,
        total_questions=5,
        progress_percentage=20.0,
    )


# ---------------------------------------------------------------------------
# get_connection_manager
# ---------------------------------------------------------------------------

class TestGetConnectionManager:
    """Test the singleton factory."""

    def test_creates_instance(self):
        """First call creates a ConnectionManager."""
        ws_routes._connection_manager = None
        mgr = ws_routes.get_connection_manager()
        assert isinstance(mgr, ConnectionManager)

    def test_returns_same_instance(self):
        """Subsequent calls return the same object."""
        ws_routes._connection_manager = None
        a = ws_routes.get_connection_manager()
        b = ws_routes.get_connection_manager()
        assert a is b

    def teardown_method(self):
        ws_routes._connection_manager = None


# ---------------------------------------------------------------------------
# get_router
# ---------------------------------------------------------------------------

class TestGetRouter:
    def test_returns_api_router(self):
        from fastapi import APIRouter
        r = ws_routes.get_router()
        assert isinstance(r, APIRouter)


# ---------------------------------------------------------------------------
# Screening WebSocket — happy path
# ---------------------------------------------------------------------------

class TestScreeningWebSocketHappyPath:
    """Full happy-path: connect → subscribe → receive messages → disconnect."""

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_connect_and_subscribe(self):
        ws = _make_mock_websocket()
        # After confirmation, client disconnects immediately
        ws.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        with patch.object(ws_routes, "get_connection_manager") as mock_get:
            mgr = ConnectionManager()
            mock_get.return_value = mgr
            await ws_routes.screening_websocket(ws, "screen-1")

        ws.accept.assert_awaited_once()
        # Should have sent "connected" confirmation
        sent = ws.send_text.call_args_list
        assert len(sent) >= 1
        confirm = json.loads(sent[0][0][0])
        assert confirm["message_type"] == "connected"
        assert confirm["screening_id"] == "screen-1"

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_sends_heartbeat_response(self):
        """Client sends heartbeat → server responds with heartbeat."""
        ws = _make_mock_websocket()
        heartbeat_msg = json.dumps({"type": "heartbeat"})
        ws.receive_text = AsyncMock(
            side_effect=[heartbeat_msg, WebSocketDisconnect()]
        )

        with patch.object(ws_routes, "get_connection_manager") as mock_get:
            mgr = ConnectionManager()
            mock_get.return_value = mgr
            await ws_routes.screening_websocket(ws, "screen-1")

        # Last call before disconnect should be the heartbeat reply
        sent_texts = [c[0][0] for c in ws.send_text.call_args_list]
        hb_replies = [t for t in sent_texts if '"heartbeat"' in t]
        assert len(hb_replies) >= 1
        parsed = json.loads(hb_replies[-1])
        assert parsed["message_type"] == "heartbeat"
        assert "timestamp" in parsed

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_ack_message_is_silent(self):
        """Client sends ack → no error, no extra reply."""
        ws = _make_mock_websocket()
        ack_msg = json.dumps({"type": "ack", "message_id": "msg-1"})
        ws.receive_text = AsyncMock(
            side_effect=[ack_msg, WebSocketDisconnect()]
        )

        with patch.object(ws_routes, "get_connection_manager") as mock_get:
            mgr = ConnectionManager()
            mock_get.return_value = mgr
            await ws_routes.screening_websocket(ws, "screen-1")

        # Only the initial "connected" message should have been sent
        sent_texts = [c[0][0] for c in ws.send_text.call_args_list]
        assert all('"connected"' in t for t in sent_texts)

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_unknown_message_type(self):
        """Client sends unknown type → logged, no crash."""
        ws = _make_mock_websocket()
        unknown_msg = json.dumps({"type": "foobar"})
        ws.receive_text = AsyncMock(
            side_effect=[unknown_msg, WebSocketDisconnect()]
        )

        with patch.object(ws_routes, "get_connection_manager") as mock_get:
            mgr = ConnectionManager()
            mock_get.return_value = mgr
            # Should not raise
            await ws_routes.screening_websocket(ws, "screen-1")


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

class TestScreeningWebSocketErrors:

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_invalid_json_logged(self):
        """Client sends non-JSON → logged warning, no crash."""
        ws = _make_mock_websocket()
        ws.receive_text = AsyncMock(
            side_effect=["not-json{{", WebSocketDisconnect()]
        )

        with patch.object(ws_routes, "get_connection_manager") as mock_get:
            mgr = ConnectionManager()
            mock_get.return_value = mgr
            await ws_routes.screening_websocket(ws, "screen-1")
        # If we got here without exception, the JSONDecodeError was handled

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_subscription_failure_sends_error(self):
        """If subscribe returns False, client receives error message."""
        ws = _make_mock_websocket()
        ws.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        with patch.object(ws_routes, "get_connection_manager") as mock_get:
            mgr = ConnectionManager()
            # Force subscribe to fail by removing the connection first
            mgr.subscribe = AsyncMock(return_value=False)
            mock_get.return_value = mgr
            await ws_routes.screening_websocket(ws, "bad-screen")

        sent_texts = [c[0][0] for c in ws.send_text.call_args_list]
        error_msgs = [t for t in sent_texts if '"error"' in t]
        assert len(error_msgs) >= 1

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_generic_exception_is_caught(self):
        """Unexpected exception → logged, connection cleaned up."""
        ws = _make_mock_websocket()
        ws.receive_text = AsyncMock(side_effect=RuntimeError("boom"))

        with patch.object(ws_routes, "get_connection_manager") as mock_get:
            mgr = ConnectionManager()
            mock_get.return_value = mgr
            await ws_routes.screening_websocket(ws, "screen-1")

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_timeout_sends_server_heartbeat(self):
        """Client goes silent → asyncio.TimeoutError → server sends heartbeat."""
        ws = _make_mock_websocket()

        with patch("backend.infrastructure.websocket.routes.asyncio.wait_for") as mock_wf:
            # First call: timeout, second call: disconnect
            mock_wf.side_effect = [asyncio.TimeoutError(), WebSocketDisconnect()]

            with patch.object(ws_routes, "get_connection_manager") as mock_get:
                mgr = ConnectionManager()
                mock_get.return_value = mgr
                await ws_routes.screening_websocket(ws, "screen-1")

        # Server should have sent a heartbeat during timeout
        sent_texts = [c[0][0] for c in ws.send_text.call_args_list]
        hb = [t for t in sent_texts if '"heartbeat"' in t]
        assert len(hb) >= 1

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_timeout_heartbeat_send_failure_breaks(self):
        """Timeout + heartbeat send failure → loop breaks."""
        ws = _make_mock_websocket()
        # Let connect and subscribe succeed, but heartbeat during timeout fails
        call_count = 0
        original_send = AsyncMock()

        async def send_side_effect(msg):
            nonlocal call_count
            call_count += 1
            if call_count > 1:  # first send = connected confirm, second = heartbeat fails
                raise Exception("closed")

        ws.send_text = AsyncMock(side_effect=send_side_effect)

        with patch("backend.infrastructure.websocket.routes.asyncio.wait_for") as mock_wf:
            mock_wf.side_effect = asyncio.TimeoutError()

            with patch.object(ws_routes, "get_connection_manager") as mock_get:
                mgr = ConnectionManager()
                mock_get.return_value = mgr
                await ws_routes.screening_websocket(ws, "screen-1")
        # Should have exited without error


# ---------------------------------------------------------------------------
# Test WebSocket endpoint
# ---------------------------------------------------------------------------

class TestTestWebSocketEndpoint:

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_echo(self):
        """Test endpoint echoes back received JSON."""
        ws = _make_mock_websocket()
        echo_data = {"foo": "bar"}
        ws.receive_text = AsyncMock(
            side_effect=[json.dumps(echo_data), WebSocketDisconnect()]
        )

        await ws_routes.test_websocket(ws)

        ws.accept.assert_awaited_once()
        sent_texts = [c[0][0] for c in ws.send_text.call_args_list]
        echo_msgs = [t for t in sent_texts if '"echo"' in t]
        assert len(echo_msgs) == 1
        parsed = json.loads(echo_msgs[0])
        assert parsed["received"] == echo_data

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_sends_connected(self):
        """Test endpoint sends connected message first."""
        ws = _make_mock_websocket()
        ws.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

        await ws_routes.test_websocket(ws)

        sent = json.loads(ws.send_text.call_args_list[0][0][0])
        assert sent["message_type"] == "connected"

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_disconnect_handled(self):
        """WebSocketDisconnect in test endpoint is silently handled."""
        ws = _make_mock_websocket()
        ws.receive_text = AsyncMock(side_effect=WebSocketDisconnect())
        await ws_routes.test_websocket(ws)  # no exception

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_generic_exception_logged(self):
        """Generic exception in test endpoint is logged."""
        ws = _make_mock_websocket()
        ws.receive_text = AsyncMock(side_effect=RuntimeError("oops"))
        await ws_routes.test_websocket(ws)  # no exception propagated


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

class TestScreeningProgressMessage:

    def test_to_dict_basic(self):
        msg = _make_progress_msg()
        d = msg.to_dict()
        assert d["message_type"] == "progress"
        assert d["screening_id"] == "s1"
        assert d["candidate_id"] == "c1"
        assert d["status"] == "STARTED"

    def test_to_dict_with_question(self):
        q = QuestionData(
            id="q1", text="Explain X", type="TECHNICAL_DEPTH",
            focus_area="Python", expected_evidence=["example"], priority="REQUIRED",
        )
        msg = ScreeningProgressMessage(
            message_type="question", screening_id="s1", candidate_id="c1",
            status="QUESTION_ASKED", current_question_number=1,
            total_questions=5, progress_percentage=20.0, current_question=q,
        )
        d = msg.to_dict()
        assert d["current_question"]["id"] == "q1"

    def test_to_dict_with_assessment(self):
        a = AssessmentData(
            quality="good", confidence=0.9, key_points_identified=["kp"],
            gaps_identified=[], decision="pass", reasoning="solid",
        )
        msg = ScreeningProgressMessage(
            message_type="assessment", screening_id="s1", candidate_id="c1",
            status="ASSESSING", current_question_number=1,
            total_questions=5, progress_percentage=20.0, latest_assessment=a,
        )
        d = msg.to_dict()
        assert d["latest_assessment"]["quality"] == "good"

    def test_to_dict_with_error(self):
        msg = ScreeningProgressMessage(
            message_type="error", screening_id="s1", candidate_id="c1",
            status="ERROR", current_question_number=0,
            total_questions=5, progress_percentage=0.0, error_message="fail",
        )
        d = msg.to_dict()
        assert d["error_message"] == "fail"

    def test_to_json(self):
        msg = _make_progress_msg()
        j = msg.to_json()
        parsed = json.loads(j)
        assert parsed["screening_id"] == "s1"

    def test_timestamp_auto_set(self):
        msg = _make_progress_msg()
        assert msg.timestamp.endswith("Z")


class TestQuestionData:
    def test_fields(self):
        q = QuestionData(
            id="q1", text="What?", type="BEHAVIORAL", focus_area="leadership",
            expected_evidence=["STAR"], priority="OPTIONAL",
        )
        assert q.id == "q1"
        assert q.priority == "OPTIONAL"


class TestAssessmentData:
    def test_fields(self):
        a = AssessmentData(
            quality="excellent", confidence=0.95,
            key_points_identified=["kp1", "kp2"],
            gaps_identified=["gap1"], decision="HIRE",
            reasoning="Strong candidate",
        )
        assert a.decision == "HIRE"
        assert len(a.key_points_identified) == 2


class TestScreeningStatus:
    def test_all_values(self):
        assert ScreeningStatus.STARTED.value == "STARTED"
        assert ScreeningStatus.COMPLETE.value == "COMPLETE"
        assert ScreeningStatus.ERROR.value == "ERROR"


# ---------------------------------------------------------------------------
# ConnectionManager
# ---------------------------------------------------------------------------

class TestConnectionManager:

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_connect(self):
        mgr = ConnectionManager()
        ws = _make_mock_websocket()
        cid = await mgr.connect(ws)
        assert cid.startswith("conn_")
        assert mgr.get_connection_count() == 1

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_disconnect(self):
        mgr = ConnectionManager()
        ws = _make_mock_websocket()
        cid = await mgr.connect(ws)
        await mgr.disconnect(cid)
        assert mgr.get_connection_count() == 0

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_subscribe_and_broadcast(self):
        mgr = ConnectionManager()
        ws = _make_mock_websocket()
        cid = await mgr.connect(ws)
        ok = await mgr.subscribe(cid, "screen-1")
        assert ok is True
        assert mgr.get_screening_subscriber_count("screen-1") == 1

        msg = _make_progress_msg("screen-1")
        count = await mgr.broadcast_to_screening("screen-1", msg)
        assert count == 1
        ws.send_text.assert_awaited()

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_subscribe_unknown_connection(self):
        mgr = ConnectionManager()
        ok = await mgr.subscribe("nope", "screen-1")
        assert ok is False

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_disconnect_cleans_subscription(self):
        mgr = ConnectionManager()
        ws = _make_mock_websocket()
        cid = await mgr.connect(ws)
        await mgr.subscribe(cid, "screen-1")
        await mgr.disconnect(cid)
        assert mgr.get_screening_subscriber_count("screen-1") == 0

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_send_to_connection(self):
        mgr = ConnectionManager()
        ws = _make_mock_websocket()
        cid = await mgr.connect(ws)
        msg = _make_progress_msg()
        ok = await mgr.send_to_connection(cid, msg)
        assert ok is True

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_send_to_unknown_connection(self):
        mgr = ConnectionManager()
        msg = _make_progress_msg()
        ok = await mgr.send_to_connection("nope", msg)
        assert ok is False

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_broadcast_send_failure_disconnects(self):
        mgr = ConnectionManager()
        ws = _make_mock_websocket()
        ws.send_text = AsyncMock(side_effect=Exception("broken"))
        cid = await mgr.connect(ws)
        await mgr.subscribe(cid, "screen-1")
        msg = _make_progress_msg("screen-1")
        count = await mgr.broadcast_to_screening("screen-1", msg)
        assert count == 0
        assert mgr.get_connection_count() == 0

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_send_failure_disconnects(self):
        mgr = ConnectionManager()
        ws = _make_mock_websocket()
        ws.send_text = AsyncMock(side_effect=Exception("broken"))
        cid = await mgr.connect(ws)
        msg = _make_progress_msg()
        ok = await mgr.send_to_connection(cid, msg)
        assert ok is False
        assert mgr.get_connection_count() == 0

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_callbacks(self):
        connect_cb = MagicMock()
        disconnect_cb = MagicMock()
        subscribe_cb = MagicMock()

        mgr = ConnectionManager()
        mgr.set_callbacks(
            on_connect=connect_cb,
            on_disconnect=disconnect_cb,
            on_subscribe=subscribe_cb,
        )
        ws = _make_mock_websocket()
        cid = await mgr.connect(ws)
        connect_cb.assert_called_once_with(cid, ws)

        await mgr.subscribe(cid, "s1")
        subscribe_cb.assert_called_once_with(cid, "s1")

        await mgr.disconnect(cid)
        disconnect_cb.assert_called_once_with(cid)

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_callback_exception_is_caught(self):
        """Callback that raises shouldn't break the manager."""
        mgr = ConnectionManager()
        mgr.set_callbacks(on_connect=MagicMock(side_effect=RuntimeError("cb")))
        ws = _make_mock_websocket()
        cid = await mgr.connect(ws)  # should not raise
        assert cid

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_resubscribe_moves_connection(self):
        mgr = ConnectionManager()
        ws = _make_mock_websocket()
        cid = await mgr.connect(ws)
        await mgr.subscribe(cid, "s1")
        await mgr.subscribe(cid, "s2")
        assert mgr.get_screening_subscriber_count("s1") == 0
        assert mgr.get_screening_subscriber_count("s2") == 1

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_broadcast_no_subscribers(self):
        mgr = ConnectionManager()
        msg = _make_progress_msg("empty")
        count = await mgr.broadcast_to_screening("empty", msg)
        assert count == 0

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_broadcast_missing_websocket_cleans_up(self):
        """If connection exists in subscribers but not in _connections,
        broadcast calls disconnect which cleans up subscribers."""
        mgr = ConnectionManager()
        # Manually insert a ghost: put it in both _connections lookup and subscriptions
        # so disconnect actually removes it from screening_subscribers
        mgr._screening_subscribers["s1"] = {"ghost"}
        mgr._subscriptions["ghost"] = "s1"
        # _connections["ghost"] does not exist, so websocket lookup fails
        msg = _make_progress_msg("s1")
        count = await mgr.broadcast_to_screening("s1", msg)
        assert count == 0
        # disconnect("ghost") removes from _subscriptions and _screening_subscribers
        assert "ghost" not in mgr._screening_subscribers.get("s1", set())

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_disconnect_close_error(self):
        """If websocket.close() raises, it's caught."""
        mgr = ConnectionManager()
        ws = _make_mock_websocket()
        ws.close = AsyncMock(side_effect=RuntimeError("already closed"))
        cid = await mgr.connect(ws)
        await mgr.disconnect(cid)  # should not raise

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_disconnect_nonexistent(self):
        """Disconnecting an unknown id is a no-op."""
        mgr = ConnectionManager()
        await mgr.disconnect("nope")  # no exception

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_send_text_awaited(self):
        """Ensure send_text is actually awaited (not called synchronously)."""
        mgr = ConnectionManager()
        ws = _make_mock_websocket()
        cid = await mgr.connect(ws)
        msg = _make_progress_msg()
        await mgr.send_to_connection(cid, msg)
        ws.send_text.assert_awaited_once()
