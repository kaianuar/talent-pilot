"""Domain service for assessing candidate answers.

This is a domain service because it encapsulates complex business logic
that doesn't naturally fit into a single entity or value object.
"""

import json
from dataclasses import dataclass
from typing import Protocol

from backend.domain.value_objects.question import Question, Answer
from backend.domain.value_objects.assessment import (
    AnswerAssessment,
    AnswerQuality,
    AssessmentDecision,
)


class LLMClient(Protocol):
    """Port for LLM client - defined here to avoid infrastructure dependency."""
    
    def complete(self, messages: list[dict], temperature: float = 0.3) -> str:
        ...


@dataclass
class AssessmentCriteria:
    """Criteria for assessing an answer."""
    
    # Minimum word count for a substantial answer
    min_word_count: int = 20
    
    # Keywords that indicate specific examples
    specificity_indicators: list[str] = None
    
    # Keywords that indicate vague/generic answers
    vague_indicators: list[str] = None
    
    def __post_init__(self):
        if self.specificity_indicators is None:
            self.specificity_indicators = [
                "for example", "specifically", "in my experience",
                "at my previous", "we implemented", "i led",
                "the project", "the system", "architecture"
            ]
        if self.vague_indicators is None:
            self.vague_indicators = [
                "comprehensive experience", "extensive knowledge",
                "strong background", "very familiar", "quite comfortable",
                "always been interested", "i'm a fast learner"
            ]


class AnswerAssessor:
    """Domain service for assessing candidate answers.
    
    Uses a hybrid approach:
    1. Heuristic pre-screening for obvious cases (vague, too short)
    2. LLM assessment for nuanced evaluation
    """
    
    def __init__(
        self,
        llm_client: LLMClient | None = None,
        criteria: AssessmentCriteria | None = None,
    ):
        self._llm = llm_client
        self._criteria = criteria or AssessmentCriteria()
    
    def assess(
        self,
        question: Question,
        answer: Answer,
        context: dict | None = None,
    ) -> AnswerAssessment:
        """Assess a candidate's answer to a screening question.
        
        Args:
            question: The question that was asked
            answer: The candidate's answer
            context: Additional context (candidate profile, job requirements, etc.)
            
        Returns:
            An AnswerAssessment with quality rating and recommended decision
        """
        # Step 1: Heuristic pre-screening
        heuristic_result = self._heuristic_assess(question, answer)
        if heuristic_result:
            return heuristic_result
        
        # Step 2: LLM assessment for nuanced evaluation
        if self._llm:
            return self._llm_assess(question, answer, context)
        
        # Fallback if no LLM available
        return AnswerAssessment(
            quality=AnswerQuality.ADEQUATE,
            confidence=0.5,
            key_points_identified=[],
            gaps_identified=["No detailed assessment available"],
            decision=AssessmentDecision.PROCEED_TO_NEXT_QUESTION,
            reasoning="Answer passed basic heuristics but no LLM available for detailed assessment",
        )
    
    def _heuristic_assess(
        self,
        question: Question,
        answer: Answer,
    ) -> AnswerAssessment | None:
        """Quick heuristic assessment for obvious cases.
        
        Returns None if heuristics are inconclusive (needs LLM assessment).
        Returns AnswerAssessment if heuristics provide clear judgment.
        """
        answer_lower = answer.text.lower()
        word_count = len(answer.text.split())
        
        # Check for obviously insufficient answers
        if word_count < self._criteria.min_word_count:
            return AnswerAssessment(
                quality=AnswerQuality.VAGUE,
                confidence=0.9,
                key_points_identified=[],
                gaps_identified=["Answer too brief", "No specific details provided"],
                decision=AssessmentDecision.PROBE_FOR_CLARITY,
                reasoning=f"Answer is only {word_count} words (minimum {self._criteria.min_word_count}). Too vague to assess.",
            )
        
        # Check for vague indicators
        vague_matches = [
            indicator for indicator in self._criteria.vague_indicators
            if indicator in answer_lower
        ]
        if len(vague_matches) >= 2:
            return AnswerAssessment(
                quality=AnswerQuality.VAGUE,
                confidence=0.85,
                key_points_identified=[],
                gaps_identified=[f"Vague language detected: {', '.join(vague_matches[:3])}"],
                decision=AssessmentDecision.PROBE_FOR_CLARITY,
                reasoning=f"Answer contains vague phrases ({', '.join(vague_matches[:3])}). Needs specific examples.",
            )
        
        # Check for strong indicators (early termination candidate)
        strong_matches = [
            indicator for indicator in self._criteria.specificity_indicators
            if indicator in answer_lower
        ]
        if len(strong_matches) >= 3 and word_count > 50:
            return AnswerAssessment(
                quality=AnswerQuality.STRONG,
                confidence=0.8,
                key_points_identified=strong_matches[:5],
                gaps_identified=[],
                decision=AssessmentDecision.SKIP_TO_EMAIL,
                reasoning=f"Strong, detailed answer with specific examples ({len(strong_matches)} specificity indicators). Sufficient evidence.",
            )
        
        # Heuristics inconclusive - needs LLM assessment
        return None
    
    def _llm_assess(
        self,
        question: Question,
        answer: Answer,
        context: dict | None,
    ) -> AnswerAssessment:
        """Use LLM for nuanced assessment."""
        
        prompt = f"""Assess this candidate's answer to a screening question.

QUESTION: {question.text}
Focus Area: {question.focus_area}
Expected Evidence: {', '.join(question.expected_evidence)}

CANDIDATE'S ANSWER: {answer.text}

Evaluate on:
1. Specificity: Did they give concrete examples or stay generic?
2. Depth: Did they demonstrate real understanding or surface knowledge?
3. Relevance: Did they actually answer the question asked?
   IMPORTANT: The answer is relevant if it addresses the QUESTION'S TOPIC.
   Do NOT assume the question is about a specific technology unless the
   question explicitly names it. A Laravel answer to an authentication
   question IS relevant — Laravel handles authentication.
4. Evidence: Did they include the expected elements?

Return as JSON:
{{
  "quality": "strong|adequate|vague|irrelevant|contradictory",
  "confidence": 0.0-1.0,
  "key_points_identified": ["specific thing 1", "specific thing 2"],
  "gaps_identified": ["missing element 1", "missing element 2"],
  "decision": "proceed_to_next|probe_for_clarity|skip_to_email|reject_candidate",
  "reasoning": "Brief feedback addressing the candidate directly using 'you/your'. Be encouraging and specific about what to improve. Max 2 sentences."
}}"""

        try:
            response = self._llm.complete(
                messages=[
                    {"role": "system", "content": "You are an expert technical recruiter. Assess candidate answers objectively."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
            )
            
            result = json.loads(response)
            
            # Parse quality with normalization — LLMs often return synonyms
            raw_quality = result.get("quality", "adequate").lower().strip()
            _quality_map = {
                "strong": AnswerQuality.STRONG,
                "excellent": AnswerQuality.STRONG,
                "good": AnswerQuality.ADEQUATE,
                "adequate": AnswerQuality.ADEQUATE,
                "acceptable": AnswerQuality.ADEQUATE,
                "moderate": AnswerQuality.ADEQUATE,
                "vague": AnswerQuality.VAGUE,
                "poor": AnswerQuality.VAGUE,
                "weak": AnswerQuality.VAGUE,
                "irrelevant": AnswerQuality.IRRELEVANT,
                "off-topic": AnswerQuality.IRRELEVANT,
                "contradictory": AnswerQuality.CONTRADICTORY,
            }
            quality = _quality_map.get(raw_quality, AnswerQuality.ADEQUATE)
            
            # Parse decision with normalization
            raw_decision = result.get("decision", "proceed_to_next").lower().strip()
            _decision_map = {
                "proceed_to_next": AssessmentDecision.PROCEED_TO_NEXT_QUESTION,
                "proceed_to_next_question": AssessmentDecision.PROCEED_TO_NEXT_QUESTION,
                "proceed": AssessmentDecision.PROCEED_TO_NEXT_QUESTION,
                "next": AssessmentDecision.PROCEED_TO_NEXT_QUESTION,
                "probe_for_clarity": AssessmentDecision.PROBE_FOR_CLARITY,
                "probe": AssessmentDecision.PROBE_FOR_CLARITY,
                "clarify": AssessmentDecision.PROBE_FOR_CLARITY,
                "skip_to_email": AssessmentDecision.SKIP_TO_EMAIL,
                "skip": AssessmentDecision.SKIP_TO_EMAIL,
                "email": AssessmentDecision.SKIP_TO_EMAIL,
                "reject_candidate": AssessmentDecision.REJECT_CANDIDATE,
                "reject": AssessmentDecision.REJECT_CANDIDATE,
            }
            decision = _decision_map.get(raw_decision, AssessmentDecision.PROCEED_TO_NEXT_QUESTION)
            
            return AnswerAssessment(
                quality=quality,
                confidence=result.get("confidence", 0.5),
                key_points_identified=result.get("key_points_identified", []),
                gaps_identified=result.get("gaps_identified", []),
                decision=decision,
                reasoning=result.get("reasoning", "No reasoning provided"),
            )
            
        except Exception as e:
            # Fallback if LLM fails entirely (network error, invalid JSON, etc.)
            return AnswerAssessment(
                quality=AnswerQuality.ADEQUATE,
                confidence=0.5,
                key_points_identified=[],
                gaps_identified=["Assessment failed"],
                decision=AssessmentDecision.PROCEED_TO_NEXT_QUESTION,
                reasoning=f"LLM assessment failed: {e}. Defaulting to proceed.",
            )
