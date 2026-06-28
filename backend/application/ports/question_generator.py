"""Primary port (driving adapter interface) for question generation.

In hexagonal architecture, this is a port that defines what the application
needs from the outside world. The actual implementation is in infrastructure.
"""

from abc import ABC, abstractmethod
from typing import Protocol

from backend.domain.value_objects.question import Question


class QuestionGenerator(Protocol):
    """Port for generating screening questions.
    
    Implementations may use LLM APIs, rule-based systems, or hybrid approaches.
    The domain doesn't care HOW questions are generated, only THAT they are.
    """
    
    @abstractmethod
    def generate_initial_questions(
        self,
        candidate_id: str,
        job_id: str,
        match_tier: str,
        count: int,
    ) -> list[Question]:
        """Generate the initial set of screening questions.
        
        Args:
            candidate_id: The candidate being screened
            job_id: The job they're being screened for
            match_tier: STRONG_MATCH, PARTIAL_MATCH, or WEAK_MATCH
            count: Number of questions to generate (1-4 depending on tier)
            
        Returns:
            List of Question value objects, ordered by priority
        """
        ...
    
    @abstractmethod
    def generate_follow_up_probe(
        self,
        original_question: Question,
        vague_answer: str,
        context: dict,
    ) -> Question:
        """Generate a probing question when an answer is vague.
        
        Args:
            original_question: The question that got a vague answer
            vague_answer: The vague answer text
            context: Additional context (candidate profile, job requirements, etc.)
            
        Returns:
            A follow-up Question that asks for specific evidence
        """
        ...
    
    @abstractmethod
    def generate_alternative_question(
        self,
        rejected_question: Question,
        rejection_reason: str,
        remaining_focus_areas: list[str],
    ) -> Question:
        """Generate an alternative when a question is rejected.
        
        This allows the human recruiter to override questions they deem inappropriate,
        and get an alternative without breaking the flow.
        
        Args:
            rejected_question: The question that was rejected
            rejection_reason: Why it was rejected
            remaining_focus_areas: What still needs to be assessed
            
        Returns:
            An alternative Question
        """
        ...
