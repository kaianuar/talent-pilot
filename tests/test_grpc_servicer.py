"""Tests for the gRPC ScreeningServicer.

Tests the gRPC servicer methods to ensure they work correctly with the
domain layer without requiring a live gRPC server.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from concurrent import futures

import grpc

# Add proto directory to path for bare imports
_proto_dir = Path(__file__).resolve().parent.parent / "backend" / "infrastructure" / "grpc" / "proto"
if str(_proto_dir) not in sys.path:
    sys.path.insert(0, str(_proto_dir))

from backend.infrastructure.grpc.proto import screening_pb2, screening_pb2_grpc
from backend.infrastructure.grpc.servicer import ScreeningServicer


@pytest.fixture
def grpc_server():
    """Create a test gRPC server with the ScreeningServicer."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=1))
    screening_pb2_grpc.add_ScreeningServiceServicer_to_server(
        ScreeningServicer(), server
    )
    port = server.add_insecure_port("[::]:0")  # random port
    server.start()
    yield port, server
    server.stop(0)


@pytest.fixture
def grpc_stub(grpc_server):
    """Create a gRPC stub connected to the test server."""
    port, _ = grpc_server
    channel = grpc.insecure_channel(f"localhost:{port}")
    stub = screening_pb2_grpc.ScreeningServiceStub(channel)
    yield stub
    channel.close()


class TestStartScreening:
    """Test the StartScreening RPC method."""

    def test_start_screening_success(self, grpc_stub):
        """StartScreening should return a valid screening ID and first question."""
        request = screening_pb2.StartScreeningRequest(
            candidate_id="test-candidate",
            job_id="test-job",
            match_tier="STRONG_MATCH",
        )
        response = grpc_stub.StartScreening(request, timeout=30)

        assert response.success is True
        assert response.screening_id  # should be non-empty
        assert response.error_message == ""
        assert response.first_question is not None
        assert response.first_question.id  # question should have an ID
        assert response.first_question.text  # question should have text

    def test_start_screening_with_question_count(self, grpc_stub):
        """StartScreening should respect the question_count parameter."""
        request = screening_pb2.StartScreeningRequest(
            candidate_id="test-candidate",
            job_id="test-job",
            match_tier="STRONG_MATCH",
            question_count=2,
        )
        response = grpc_stub.StartScreening(request, timeout=30)

        assert response.success is True
        assert response.screening_id


class TestSubmitAnswer:
    """Test the SubmitAnswer RPC method."""

    def test_submit_answer_returns_assessment(self, grpc_stub):
        """SubmitAnswer should return an assessment for the answer."""
        # First start a screening
        start_req = screening_pb2.StartScreeningRequest(
            candidate_id="test-candidate",
            job_id="test-job",
            match_tier="STRONG_MATCH",
        )
        start_resp = grpc_stub.StartScreening(start_req, timeout=30)
        screening_id = start_resp.screening_id

        # Submit an answer
        answer_req = screening_pb2.SubmitAnswerRequest(
            screening_id=screening_id,
            candidate_id="test-candidate",
            question_id=start_resp.first_question.id,
            answer_text="I have extensive experience with Python and distributed systems.",
        )
        answer_resp = grpc_stub.SubmitAnswer(answer_req, timeout=30)

        # Should have an assessment
        assert answer_resp.assessment is not None
        assert answer_resp.assessment.quality  # should have a quality rating

    def test_submit_answer_returns_next_question(self, grpc_stub):
        """SubmitAnswer should return the next question if not complete."""
        start_req = screening_pb2.StartScreeningRequest(
            candidate_id="test-candidate",
            job_id="test-job",
            match_tier="STRONG_MATCH",
            question_count=3,
        )
        start_resp = grpc_stub.StartScreening(start_req, timeout=30)
        screening_id = start_resp.screening_id

        # Submit answer to first question
        answer_req = screening_pb2.SubmitAnswerRequest(
            screening_id=screening_id,
            candidate_id="test-candidate",
            question_id=start_resp.first_question.id,
            answer_text="I have 5 years of experience with React and Node.js.",
        )
        answer_resp = grpc_stub.SubmitAnswer(answer_req, timeout=30)

        # Should have next question (not complete yet)
        if not answer_resp.is_complete:
            assert answer_resp.next_question is not None
            assert answer_resp.next_question.text


class TestGetScreeningResult:
    """Test the GetScreeningResult RPC method."""

    def test_get_screening_result(self, grpc_stub):
        """GetScreeningResult should return a summary after screening."""
        # Start and complete a screening
        start_req = screening_pb2.StartScreeningRequest(
            candidate_id="test-candidate",
            job_id="test-job",
            match_tier="STRONG_MATCH",
            question_count=1,  # minimal for quick test
        )
        start_resp = grpc_stub.StartScreening(start_req, timeout=30)
        screening_id = start_resp.screening_id

        # Submit answer
        answer_req = screening_pb2.SubmitAnswerRequest(
            screening_id=screening_id,
            candidate_id="test-candidate",
            question_id=start_resp.first_question.id,
            answer_text="I have extensive experience with the required technologies.",
        )
        grpc_stub.SubmitAnswer(answer_req, timeout=30)

        # Get result
        result_req = screening_pb2.GetScreeningResultRequest(
            screening_id=screening_id,
            candidate_id="test-candidate",
        )
        result_resp = grpc_stub.GetScreeningResult(result_req, timeout=30)

        assert result_resp.success is True
        assert result_resp.summary is not None
        assert result_resp.summary.screening_id == screening_id


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_submit_answer_unknown_session(self, grpc_stub):
        """SubmitAnswer should handle unknown screening ID gracefully."""
        answer_req = screening_pb2.SubmitAnswerRequest(
            screening_id="nonexistent-id",
            candidate_id="test-candidate",
            question_id="q1",
            answer_text="test",
        )
        # Should get an error or empty response
        try:
            answer_resp = grpc_stub.SubmitAnswer(answer_req, timeout=10)
            # If it returns, it should indicate failure
            assert answer_resp.assessment.quality == "" or answer_resp.is_complete
        except grpc.RpcError as e:
            # Expected - NOT_FOUND or similar
            assert e.code() in [grpc.StatusCode.NOT_FOUND, grpc.StatusCode.INTERNAL]
