"""Infrastructure adapter implementing AnswerAssessor as an LLM-backed service."""

from openai import OpenAI

from backend.domain.services.answer_assessor import AnswerAssessor
from backend.config import QWEN_API_KEY, QWEN_BASE_URL, MODEL_REASONING


class _OpenAIAdapter:
    """Wraps an OpenAI client to match the LLMClient protocol (single `complete` method)."""

    def __init__(self, client: OpenAI, model: str):
        self._client = client
        self._model = model

    def complete(self, messages: list[dict], temperature: float = 0.3) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=temperature,
            max_tokens=1000,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content


class LLMAnswerAssessor(AnswerAssessor):
    """Adapter that injects the Qwen LLM client into the AnswerAssessor."""

    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        client = OpenAI(
            base_url=base_url or QWEN_BASE_URL,
            api_key=api_key or QWEN_API_KEY,
        )
        resolved_model = model or MODEL_REASONING
        super().__init__(llm_client=_OpenAIAdapter(client, resolved_model))
