"""Infrastructure adapter implementing QuestionGenerator port with LLM."""

import json
import uuid
from typing import Protocol

from openai import OpenAI

from backend.application.ports.question_generator import QuestionGenerator
from backend.domain.value_objects.question import Question, QuestionType, QuestionPriority
from backend.config import QWEN_API_KEY, QWEN_BASE_URL, MODEL_REASONING


class LLMQuestionGenerator(QuestionGenerator):
    """Adapter that uses LLM (Qwen) to generate screening questions."""
    
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self.api_key = api_key or QWEN_API_KEY
        self.base_url = base_url or QWEN_BASE_URL
        self.model = model or MODEL_REASONING
        self._client: OpenAI | None = None
    
    @property
    def client(self) -> OpenAI:
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            self._client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
            )
        return self._client
    
    def generate_initial_questions(
        self,
        candidate_id: str,
        job_id: str,
        match_tier: str,
        count: int,
    ) -> list[Question]:
        """Generate initial screening questions via LLM."""
        
        prompt = self._build_question_generation_prompt(
            candidate_id=candidate_id,
            job_id=job_id,
            match_tier=match_tier,
            count=count,
        )
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert technical recruiter. Generate focused, specific screening questions."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=800,
            response_format={"type": "json_object"},
        )
        
        raw_content = response.choices[0].message.content
        questions_data = json.loads(raw_content)
        
        if isinstance(questions_data, dict) and "questions" in questions_data:
            questions_list = questions_data["questions"]
        elif isinstance(questions_data, list):
            questions_list = questions_data
        else:
            questions_list = [questions_data]
        
        return self._parse_questions(questions_list)
    
    def generate_follow_up_probe(
        self,
        original_question: Question,
        vague_answer: str,
        context: dict,
    ) -> Question:
        """Generate a probing question for vague answers."""
        
        prompt = f"""The candidate gave a vague answer to this question:

Original Question: {original_question.text}

Candidate's Vague Answer: {vague_answer}

Generate a follow-up question that probes for SPECIFIC evidence:
- Ask for a concrete example or project
- Ask about scale, complexity, or metrics
- Ask about duration and their specific role

Return as JSON:
{{"text": "your probing question here", "type": "gap_probe", "focus_area": "{original_question.focus_area}"}}"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert technical recruiter. Generate probing follow-up questions."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=200,
            response_format={"type": "json_object"},
        )
        
        data = json.loads(response.choices[0].message.content)
        
        return Question(
            id=str(uuid.uuid4()),
            text=data["text"],
            type=QuestionType.GAP_PROBE,
            priority=QuestionPriority.REQUIRED,
            focus_area=data.get("focus_area", original_question.focus_area),
            expected_evidence=["Specific project name", "Technical details", "Their specific contribution"],
            follow_up_trigger=None,
        )
    
    def generate_alternative_question(
        self,
        rejected_question: Question,
        rejection_reason: str,
        remaining_focus_areas: list[str],
    ) -> Question:
        """Generate an alternative when a question is rejected."""
        # Simplified implementation - in production, this would use LLM
        return Question(
            id=str(uuid.uuid4()),
            text=f"[Alternative to: {rejected_question.text[:50]}...]",
            type=QuestionType.TECHNICAL_DEPTH,
            priority=QuestionPriority.IMPORTANT,
            focus_area=remaining_focus_areas[0] if remaining_focus_areas else "general",
            expected_evidence=["Specific example"],
            follow_up_trigger=None,
        )
    
    def _build_question_generation_prompt(
        self,
        candidate_id: str,
        job_id: str,
        match_tier: str,
        count: int,
    ) -> str:
        """Build the prompt for question generation."""
        return f"""Generate {count} screening questions for a candidate interviewing for a job.

Match Tier: {match_tier}
- STRONG_MATCH: 1-2 questions, focus on confirming strong fit
- PARTIAL_MATCH: 2-3 questions, focus on assessing gaps
- WEAK_MATCH: 3-4 questions, focus on transferable skills

Guidelines:
1. Each question should be specific and focused on ONE skill or experience area
2. Ask for concrete examples, not hypotheticals
3. Questions should be answerable in 1-2 sentences
4. Order by priority (most important skill gaps first)

Return as JSON array:
[
  {{
    "text": "The actual question text here",
    "type": "technical_depth|experience_verification|problem_solving|culture_fit",
    "focus_area": "e.g., React hooks",
    "expected_evidence": ["specific project name", "technical detail 1", "technical detail 2"]
  }},
  ...
]"""
    
    def _parse_questions(self, data: list[dict]) -> list[Question]:
        """Parse question data from LLM response."""
        questions = []
        
        type_mapping = {
            "technical_depth": QuestionType.TECHNICAL_DEPTH,
            "experience_verification": QuestionType.EXPERIENCE_VERIFICATION,
            "problem_solving": QuestionType.PROBLEM_SOLVING,
            "culture_fit": QuestionType.CULTURE_FIT,
            "gap_probe": QuestionType.GAP_PROBE,
        }
        
        for i, q_data in enumerate(data):
            q_type = type_mapping.get(q_data.get("type"), QuestionType.TECHNICAL_DEPTH)
            
            questions.append(Question(
                id=str(uuid.uuid4()),
                text=q_data["text"],
                type=q_type,
                priority=QuestionPriority.REQUIRED if i == 0 else QuestionPriority.IMPORTANT,
                focus_area=q_data.get("focus_area", "general"),
                expected_evidence=q_data.get("expected_evidence", []),
                follow_up_trigger=None,
            ))
        
        return questions
