# Qwen Cloud API Spec

## Endpoint

**DashScope International (Singapore)**
```
Base URL: https://dashscope-intl.aliyuncs.com/compatible-mode/v1
Protocol: OpenAI-compatible (works with `openai` Python SDK)
```

## Authentication

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    api_key="your-qwen-cloud-api-key"
)
```

Get API key: https://home.qwencloud.com/api-keys

## Models Used

### Qwen3-VL-Plus (Vision)
- **Model ID**: `qwen3-vl-plus`
- **Use case**: CV/Resume PDF parsing
- **Capabilities**: Vision + OCR, multimodal input
- **Input**: Base64-encoded PDF as image_url
- **Output**: Structured JSON

**Usage**:
```python
response = client.chat.completions.create(
    model="qwen3-vl-plus",
    messages=[
        {"role": "system", "content": "Extract structured data..."},
        {"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:application/pdf;base64,{b64}"}},
            {"type": "text", "text": "Parse this resume."}
        ]}
    ],
    temperature=0.1,
    max_tokens=2000
)
```

### qwen3-max (Reasoning)
- **Model ID**: `qwen3-max`
- **Use case**: Match reasoning, screening questions, email drafting
- **Capabilities**: Chat, reasoning, function calling
- **Temperature**: 0.2-0.3 for deterministic outputs

**Usage**:
```python
response = client.chat.completions.create(
    model="qwen3-max",
    messages=[
        {"role": "system", "content": "You are a recruiting analyst."},
        {"role": "user", "content": "Rate this fit 0.0-1.0..."}
    ],
    temperature=0.2,
    max_tokens=200
)
```

### qwen-turbo (Chat)
- **Model ID**: `qwen-turbo`
- **Use case**: Lightweight chat responses (optional)
- **Capabilities**: Fast chat, lower cost

## Function Calling

OpenAI-compatible tool definitions:

```python
tools = [{
    "type": "function",
    "function": {
        "name": "tool_name",
        "description": "What the tool does",
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {"type": "string", "description": "..."}
            },
            "required": ["param1"]
        }
    }
}]

response = client.chat.completions.create(
    model="qwen3-max",
    messages=messages,
    tools=tools,
    tool_choice="auto"
)
```

## Error Handling

| Error Code | Meaning | Action |
|------------|---------|--------|
| 401 | Invalid API key | Check key, redirect to setup |
| 429 | Rate limit | Exponential backoff |
| 500 | Server error | Retry with backoff |
| 503 | Model unavailable | Fallback to alternative model |

## Cost Management

- **Voucher**: $40 cloud credits
- **Caching**: Cache LLM results keyed by (candidate_id, job_id)
- **Model selection**: Use qwen-turbo for simple tasks, qwen3-max for reasoning
- **Batching**: Combine multiple requests where possible

## Setup Checklist

1. Register at https://www.qwencloud.com/challenge/hackathon/voucher-application
2. Create API key at https://home.qwencloud.com/api-keys
3. Store in environment: `QWEN_API_KEY=your-key`
4. Test connection: `client.models.list()`
5. Test vision: Send a sample PDF to Qwen3-VL-Plus
6. Test reasoning: Send a match prompt to qwen3-max

## Available Models (Reference)

| Model | ID | Best For |
|-------|----|----------|
| Qwen3-Max | qwen3-max | Complex reasoning, function calling |
| Qwen3-Plus | qwen3-plus | General purpose |
| Qwen3-Turbo | qwen-turbo | Fast, low-cost chat |
| Qwen3-VL-Plus | qwen3-vl-plus | Vision, OCR, PDF parsing |
| Qwen3-VL-Flash | qwen3-vl-flash | Fast vision tasks |
| Qwen3-Coder-Plus | qwen3-coder-plus | Code generation |

## Region

Singapore region for lowest latency to international users.
Base URL is region-specific — change `QWEN_BASE_URL` env var for other regions.
