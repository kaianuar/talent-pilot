"""Tests for AnswerAssessor domain service.

Covers heuristic pre-screening, LLM assessment (mocked), quality ratings,
decision routing, and fallback paths.
"""

import json
import pytest
from unittest.mock import MagicMock

from backend.domain.services.answer_assessor import (
    AnswerAssessor,
    AssessmentCriteria,
    LLMClient,
)
from backend.domain.value_objects.question import (
    Question,
    Answer,
    QuestionType,
    QuestionPriority,
)
from backend.domain.value_objects.assessment import (
    AnswerAssessment,
    AnswerQuality,
    AssessmentDecision,
)


# --- Fixtures ---


@pytest.fixture
def sample_question() -> Question:
    """A representative screening question."""
    return Question(
        id="q1",
        text="Describe a time you designed a scalable system.",
        type=QuestionType.TECHNICAL_DEPTH,
        priority=QuestionPriority.REQUIRED,
        focus_area="System Design",
        expected_evidence=["architecture diagram", "trade-offs discussed", "load metrics"],
    )


def _make_answer(text: str, qid: str = "q1") -> Answer:
    return Answer(question_id=qid, text=text, timestamp=1700000000.0)


@pytest.fixture
def short_answer() -> Answer:
    """Answer shorter than min_word_count."""
    return _make_answer("I have extensive knowledge in backend.")


@pytest.fixture
def vague_answer() -> Answer:
    """Answer that meets length but uses vague phrases (>=2 vague indicators)."""
    text = (
        "I have comprehensive experience and extensive knowledge in building "
        "distributed systems. My strong background includes working with "
        "microservices and I am quite comfortable with cloud platforms. "
        "I have always been interested in scalable architectures and believe "
        "my skills would be a great fit for this role."
    )
    return _make_answer(text)


@pytest.fixture
def strong_answer() -> Answer:
    """Long answer with >= 3 specificity indicators and > 50 words."""
    text = (
        "In my experience at Acme Corp, we implemented a new event-driven "
        "architecture for our order processing system. Specifically, I led "
        "the migration from a monolithic design to microservices. "
        "For example, the project involved decomposing the payment service "
        "into three separate services. The system I designed handled "
        "over 10,000 requests per second with 99.9% uptime. "
        "The architecture used Kafka for event streaming and PostgreSQL "
        "for persistent storage. We also implemented circuit breakers "
        "to handle downstream service failures gracefully."
    )
    return _make_answer(text)


@pytest.fixture
def adequate_answer() -> Answer:
    """Answer that passes heuristics but isn't strong — needs LLM."""
    text = (
        "I worked on a project where we moved from a monolith to microservices "
        "architecture. It was a challenging experience that taught me a lot "
        "about distributed systems and the importance of good API design. "
        "I collaborated with the team to ensure smooth deployment."
    )
    return _make_answer(text)


@pytest.fixture
def mock_llm_client() -> MagicMock:
    """A mock LLM client that returns a strong assessment by default."""
    client = MagicMock(spec=LLMClient)
    client.complete.return_value = json.dumps({
        "quality": "strong",
        "confidence": 0.9,
        "key_points_identified": ["described architecture", "discussed trade-offs"],
        "gaps_identified": [],
        "decision": "proceed_to_next",
        "reasoning": "Candidate gave specific, relevant examples with depth.",
    })
    return client


@pytest.fixture
def assessor(mock_llm_client) -> AnswerAssessor:
    return AnswerAssessor(llm_client=mock_llm_client)


@pytest.fixture
def heuristic_only_assessor() -> AnswerAssessor:
    """Assessor with no LLM — heuristic only."""
    return AnswerAssessor(llm_client=None)


# --- AssessmentCriteria tests ---


class TestAssessmentCriteria:
    def test_defaults(self):
        c = AssessmentCriteria()
        assert c.min_word_count == 20
        assert isinstance(c.specificity_indicators, list)
        assert len(c.specificity_indicators) > 0
        assert isinstance(c.vague_indicators, list)
        assert len(c.vague_indicators) > 0

    def test_custom_values(self):
        c = AssessmentCriteria(
            min_word_count=10,
            specificity_indicators=["custom"],
            vague_indicators=["bad"],
        )
        assert c.min_word_count == 10
        assert c.specificity_indicators == ["custom"]
        assert c.vague_indicators == ["bad"]


# --- Heuristic pre-screening ---


class TestHeuristicAssess:
    def test_short_answer_returns_vague(self, assessor, sample_question, short_answer):
        result = assessor._heuristic_assess(sample_question, short_answer)
        assert result is not None
        assert result.quality == AnswerQuality.VAGUE
        assert result.decision == AssessmentDecision.PROBE_FOR_CLARITY
        assert result.confidence == 0.9
        assert any("brief" in g.lower() for g in result.gaps_identified)

    def test_vague_indicators_detected(self, assessor, sample_question, vague_answer):
        result = assessor._heuristic_assess(sample_question, vague_answer)
        assert result is not None
        assert result.quality == AnswerQuality.VAGUE
        assert result.decision == AssessmentDecision.PROBE_FOR_CLARITY
        assert result.confidence == 0.85

    def test_single_vague_indicator_not_flagged(self, assessor, sample_question):
        """Only 1 vague indicator should not trigger heuristic vagueness."""
        text = (
            "I have extensive knowledge in system design. Let me describe "
            "a specific architecture I built using Kafka and PostgreSQL "
            "for handling real-time event processing at scale."
        )
        answer = _make_answer(text)
        result = assessor._heuristic_assess(sample_question, answer)
        # 1 vague indicator alone shouldn't trigger; heuristics inconclusive
        assert result is None

    def test_strong_answer_detected(self, assessor, sample_question, strong_answer):
        result = assessor._heuristic_assess(sample_question, strong_answer)
        assert result is not None
        assert result.quality == AnswerQuality.STRONG
        assert result.decision == AssessmentDecision.SKIP_TO_EMAIL
    def test_strong_indicators_short_text_not_flagged(self, assessor, sample_question):
        """>= 3 specificity indicators but <= 50 words → no heuristic strong."""
        text = (
            "In my experience we implemented the project at a large scale. "
            "Specifically I led the architecture design for the new platform. "
            "The project involved multiple services and careful planning "
            "across teams to ensure everything worked correctly together."
        )
        answer = _make_answer(text)
        result = assessor._heuristic_assess(sample_question, answer)
        assert result is None  # inconclusive — word count > 20 but < 50

    def test_inconclusive_returns_none(self, assessor, sample_question, adequate_answer):
        result = assessor._heuristic_assess(sample_question, adequate_answer)
        assert result is None


# --- LLM assessment (mocked) ---


class TestLLMAssess:
    def test_successful_llm_assessment(self, assessor, sample_question, adequate_answer, mock_llm_client):
        result = assessor._llm_assess(sample_question, adequate_answer, context=None)
        assert result.quality == AnswerQuality.STRONG
        assert result.confidence == 0.9
        assert len(result.key_points_identified) == 2
        assert result.decision == AssessmentDecision.PROCEED_TO_NEXT_QUESTION
        mock_llm_client.complete.assert_called_once()

    def test_llm_receives_question_and_answer(self, assessor, sample_question, adequate_answer, mock_llm_client):
        assessor._llm_assess(sample_question, adequate_answer, context={"candidate": "Jane"})
        call_args = mock_llm_client.complete.call_args
        messages = call_args.kwargs["messages"] if call_args.kwargs else call_args[1]["messages"]
        user_msg = messages[1]["content"]
        assert sample_question.text in user_msg
        assert adequate_answer.text in user_msg

    def test_llm_returns_all_quality_ratings(self, assessor, sample_question, adequate_answer, mock_llm_client):
        for quality in ["strong", "adequate", "vague", "irrelevant", "contradictory"]:
            mock_llm_client.complete.return_value = json.dumps({
                "quality": quality,
                "confidence": 0.7,
                "key_points_identified": [],
                "gaps_identified": [],
                "decision": "proceed_to_next",
                "reasoning": f"Testing {quality}.",
            })
            result = assessor._llm_assess(sample_question, adequate_answer, None)
            assert result.quality == quality

    def test_llm_returns_all_decisions(self, assessor, sample_question, adequate_answer, mock_llm_client):
        for decision in ["proceed_to_next", "probe_for_clarity", "skip_to_email", "reject_candidate"]:
            mock_llm_client.complete.return_value = json.dumps({
                "quality": "adequate",
                "confidence": 0.7,
                "key_points_identified": [],
                "gaps_identified": [],
                "decision": decision,
                "reasoning": f"Testing {decision}.",
            })
            result = assessor._llm_assess(sample_question, adequate_answer, None)
            assert result.decision == decision

    def test_llm_failure_returns_fallback(self, assessor, sample_question, adequate_answer, mock_llm_client):
        mock_llm_client.complete.side_effect = RuntimeError("API timeout")
        result = assessor._llm_assess(sample_question, adequate_answer, None)
        assert result.quality == AnswerQuality.ADEQUATE
        assert result.confidence == 0.5
        assert result.decision == AssessmentDecision.PROCEED_TO_NEXT_QUESTION
        assert "failed" in result.reasoning.lower()

    def test_llm_returns_invalid_json_fallback(self, assessor, sample_question, adequate_answer, mock_llm_client):
        mock_llm_client.complete.return_value = "not json at all"
        result = assessor._llm_assess(sample_question, adequate_answer, None)
        assert result.quality == AnswerQuality.ADEQUATE
        assert "failed" in result.reasoning.lower()


# --- Full assess() flow ---


class TestAssessFlow:
    def test_short_answer_skips_llm(self, assessor, sample_question, short_answer, mock_llm_client):
        """Short answer is caught by heuristics; LLM is never called."""
        result = assessor.assess(sample_question, short_answer)
        assert result.quality == AnswerQuality.VAGUE
        mock_llm_client.complete.assert_not_called()

    def test_vague_answer_skips_llm(self, assessor, sample_question, vague_answer, mock_llm_client):
        result = assessor.assess(sample_question, vague_answer)
        assert result.quality == AnswerQuality.VAGUE
        mock_llm_client.complete.assert_not_called()

    def test_strong_answer_skips_llm(self, assessor, sample_question, strong_answer, mock_llm_client):
        result = assessor.assess(sample_question, strong_answer)
        assert result.quality == AnswerQuality.STRONG
        assert result.decision == AssessmentDecision.SKIP_TO_EMAIL
        mock_llm_client.complete.assert_not_called()

    def test_adequate_answer_goes_to_llm(self, assessor, sample_question, adequate_answer, mock_llm_client):
        result = assessor.assess(sample_question, adequate_answer)
        mock_llm_client.complete.assert_called_once()
        assert result.quality == AnswerQuality.STRONG  # from mock

    def test_no_llm_fallback(self, heuristic_only_assessor, sample_question, adequate_answer):
        """When no LLM, inconclusive heuristics fall back to default ADEQUATE."""
        result = heuristic_only_assessor.assess(sample_question, adequate_answer)
        assert result.quality == AnswerQuality.ADEQUATE
        assert result.confidence == 0.5
        assert result.decision == AssessmentDecision.PROCEED_TO_NEXT_QUESTION
        assert "no llm" in result.reasoning.lower()

    def test_no_llm_short_answer_still_catches(self, heuristic_only_assessor, sample_question, short_answer):
        """Even without LLM, heuristics still catch short answers."""
        result = heuristic_only_assessor.assess(sample_question, short_answer)
        assert result.quality == AnswerQuality.VAGUE
        assert result.decision == AssessmentDecision.PROBE_FOR_CLARITY

    def test_custom_criteria(self, sample_question, mock_llm_client):
        """Custom criteria change thresholds."""
        criteria = AssessmentCriteria(min_word_count=5)
        assessor = AnswerAssessor(llm_client=mock_llm_client, criteria=criteria)
        # This would normally be "too short" with default min_word_count=20
        answer = _make_answer("I built a distributed system with microservices and Kafka.")
        result = assessor.assess(sample_question, answer)
        # Should pass heuristics (>=5 words) and go to LLM
        mock_llm_client.complete.assert_called_once()

    def test_assess_with_context(self, assessor, sample_question, adequate_answer, mock_llm_client):
        context = {"candidate_name": "Jane Doe", "years_experience": 8}
        assessor.assess(sample_question, adequate_answer, context=context)
        call_args = mock_llm_client.complete.call_args
        # Context is passed through — the prompt doesn't need to contain it explicitly
        # but the call should succeed
        assert call_args is not None


# --- AnswerAssessment value object ---


class TestAnswerAssessmentVO:
    def test_is_sufficient_for_tier_strong_match(self):
        for quality in [AnswerQuality.ADEQUATE, AnswerQuality.STRONG]:
            assessment = AnswerAssessment(
                quality=quality, confidence=0.9,
                key_points_identified=[], gaps_identified=[],
                decision=AssessmentDecision.PROCEED_TO_NEXT_QUESTION,
                reasoning="test",
            )
            assert assessment.is_sufficient_for_tier("STRONG_MATCH")

    def test_is_sufficient_for_tier_weak_match(self):
        assessment = AnswerAssessment(
            quality=AnswerQuality.VAGUE, confidence=0.5,
            key_points_identified=[], gaps_identified=[],
            decision=AssessmentDecision.PROBE_FOR_CLARITY,
            reasoning="test",
        )
        assert assessment.is_sufficient_for_tier("PARTIAL_MATCH")
        assert assessment.is_sufficient_for_tier("WEAK_MATCH")
        assert not assessment.is_sufficient_for_tier("STRONG_MATCH")

    def test_is_sufficient_for_tier_irrelevant_fails(self):
        assessment = AnswerAssessment(
            quality=AnswerQuality.IRRELEVANT, confidence=0.9,
            key_points_identified=[], gaps_identified=[],
            decision=AssessmentDecision.REJECT_CANDIDATE,
            reasoning="test",
        )
        assert not assessment.is_sufficient_for_tier("STRONG_MATCH")
        assert not assessment.is_sufficient_for_tier("PARTIAL_MATCH")
        assert not assessment.is_sufficient_for_tier("WEAK_MATCH")

    def test_is_sufficient_for_unknown_tier(self):
        assessment = AnswerAssessment(
            quality=AnswerQuality.ADEQUATE, confidence=0.8,
            key_points_identified=[], gaps_identified=[],
            decision=AssessmentDecision.PROCEED_TO_NEXT_QUESTION,
            reasoning="test",
        )
        # Unknown tier defaults to VAGUE threshold
        assert assessment.is_sufficient_for_tier("UNKNOWN_TIER")
