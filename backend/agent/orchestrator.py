"""TalentPilot agent orchestrator using Qwen-Agent with tool-calling loop."""

import json
import logging
import re
from typing import Any

from openai import OpenAI

from backend.config import QWEN_API_KEY, QWEN_BASE_URL, MODEL_REASONING
from backend.agent.prompts import SYSTEM_PROMPT
from backend.agent.tools import (
    parse_resume_tool,
    list_jobs_tool,
    match_jobs_tool,
    generate_screening_questions_tool,
    confirm_and_draft_email_tool,
    send_email_tool,
)

logger = logging.getLogger(__name__)

# Map tool names to functions
TOOL_MAP = {
    "parse_resume_tool": parse_resume_tool,
    "list_jobs_tool": list_jobs_tool,
    "match_jobs_tool": match_jobs_tool,
    "generate_screening_questions_tool": generate_screening_questions_tool,
    "confirm_and_draft_email_tool": confirm_and_draft_email_tool,
    "send_email_tool": send_email_tool,
}

# OpenAI-compatible tool definitions
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "parse_resume_tool",
            "description": "Parse a CV/resume PDF file and extract structured candidate information (name, email, phone, skills, experiences, education, years_experience).",
            "parameters": {
                "type": "object",
                "properties": {
                    "pdf_path": {"type": "string", "description": "Path to the PDF file on disk."},
                },
                "required": ["pdf_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_jobs_tool",
            "description": "List all available job openings at the company. Returns job summaries with id, title, company.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "match_jobs_tool",
            "description": "Match a candidate against all available jobs and return top-5 ranked results with scores and reasoning. Use this when the candidate asks about job matches or suitability.",
            "parameters": {
                "type": "object",
                "properties": {
                    "candidate_id": {"type": "string", "description": "The candidate's unique identifier."},
                },
                "required": ["candidate_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_screening_questions_tool",
            "description": "Generate 2-3 targeted screening questions for a candidate-job pair based on skill gaps.",
            "parameters": {
                "type": "object",
                "properties": {
                    "candidate_id": {"type": "string", "description": "The candidate's unique identifier."},
                    "job_id": {"type": "string", "description": "The job's unique identifier."},
                },
                "required": ["candidate_id", "job_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "confirm_and_draft_email_tool",
            "description": "Draft a professional email to the recruiter for the candidate to review. Does NOT send the email.",
            "parameters": {
                "type": "object",
                "properties": {
                    "candidate_id": {"type": "string", "description": "The candidate's unique identifier."},
                    "job_id": {"type": "string", "description": "The job's unique identifier."},
                    "screening_answers": {
                        "type": "object",
                        "description": "Dict of question -> answer pairs from the screening step.",
                        "additionalProperties": {"type": "string"},
                    },
                },
                "required": ["candidate_id", "job_id", "screening_answers"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_email_tool",
            "description": "Send a draft email to the recruiter via DirectMail. Only call this after the candidate has explicitly confirmed they want to send.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address."},
                    "subject": {"type": "string", "description": "Email subject."},
                    "body": {"type": "string", "description": "Email body text."},
                    "candidate_id": {"type": "string", "description": "The candidate's ID for audit logging."},
                },
                "required": ["to", "subject", "body", "candidate_id"],
            },
        },
    },
]


def _execute_tool(name: str, arguments: dict, send_confirmed: bool) -> str:
    """Execute a tool by name with the given arguments.

    Enforces human-in-the-loop: send_email_tool is blocked unless send_confirmed=True.
    """
    if name == "send_email_tool" and not send_confirmed:
        logger.warning("Blocked send_email_tool call: send_confirmed=False")
        return json.dumps({
            "status": "blocked",
            "message": "I need your explicit confirmation before sending. Please click 'Send' on the email preview."
        })

    func = TOOL_MAP.get(name)
    if not func:
        return json.dumps({"error": f"Unknown tool: {name}"})

    try:
        return func(**arguments)
    except Exception as e:
        logger.exception("Tool %s failed", name)
        return json.dumps({"error": f"Tool {name} failed: {e}"})


def run_turn(
    messages: list[dict],
    candidate_id: str,
    pdf_path: str | None = None,
    send_confirmed: bool = False,
    max_tool_rounds: int = 10,
) -> tuple[list[dict], str]:
    """Run one conversation turn through the agent.

    Args:
        messages: Conversation history (list of {role, content} dicts).
        candidate_id: The current candidate's ID.
        pdf_path: If set, the agent will parse this CV on the first turn.
        send_confirmed: Whether the user has explicitly confirmed sending.
        max_tool_rounds: Max tool-call rounds before forcing a text response.

    Returns:
        (updated_messages, assistant_text)
    """
    if not QWEN_API_KEY:
        raise RuntimeError("QWEN_API_KEY not configured.")

    client = OpenAI(base_url=QWEN_BASE_URL, api_key=QWEN_API_KEY)

    # Build the system prompt with candidate context
    system_content = SYSTEM_PROMPT + f"\n\nCurrent candidate_id: {candidate_id}"

    if pdf_path:
        # CV just uploaded — tell agent to parse it
        system_content += f"\n\nThe candidate has uploaded a CV at: {pdf_path}. Use parse_resume_tool to process it, then use match_jobs_tool to find suitable jobs."
    else:
        # CV already parsed — tell agent the data is available
        system_content += (
            f"\n\nIMPORTANT: The candidate's CV has already been parsed and their data is stored in the system. "
            f"When the candidate asks about jobs, matches, or suitability, you MUST call match_jobs_tool with "
            f"candidate_id='{candidate_id}' to retrieve their parsed resume and find matching jobs. "
            f"Do NOT ask them to upload a CV — it's already been processed."
        )

    agent_messages = [{"role": "system", "content": system_content}]
    agent_messages.extend(messages)

    assistant_text = ""

    for round_num in range(max_tool_rounds):
        try:
            response = client.chat.completions.create(
                model=MODEL_REASONING,
                messages=agent_messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
                temperature=0.3,
                max_tokens=2000,
            )
        except Exception as e:
            logger.exception("LLM call failed on round %d", round_num)
            assistant_text = f"I encountered an error: {e}. Please try again."
            break

        choice = response.choices[0]
        msg = choice.message

        # If no tool calls, we're done
        if not msg.tool_calls:
            assistant_text = msg.content or ""
            agent_messages.append({"role": "assistant", "content": assistant_text})
            break

        # Process tool calls
        agent_messages.append(msg)

        for tc in msg.tool_calls:
            func_name = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}

            logger.info("Tool call: %s(%s)", func_name, args)
            result = _execute_tool(func_name, args, send_confirmed)
            logger.info("Tool result: %s", result[:200])

            agent_messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })
    else:
        # Exhausted rounds
        assistant_text = "I've processed your request. How can I help you further?"
        agent_messages.append({"role": "assistant", "content": assistant_text})

    return messages + [{"role": "assistant", "content": assistant_text}], assistant_text
