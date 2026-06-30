"""Infrastructure adapter implementing AnswerAssessor as an LLM-backed service."""

from openai import OpenAI

from backend.domain.services.answer_assessor import AnswerAssessor
from backend.config import QWEN_API_KEY, QWEN_BASE_URL, MODEL_REASONING


class LLMAnswerAssessor(AnswerAssessor):
    """Adapter that injects the Qwen LLM client into the AnswerAssessor."""

    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        client = OpenAI(
            base_url=base_url or QWEN_BASE_URL,
            api_key=api_key or QWEN_API_KEY,
        )
        super().__init__(llm_client=client)
