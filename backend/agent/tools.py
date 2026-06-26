"""MCP-style tools for the TalentPilot agent.

Each tool is a plain function with a docstring that Qwen-Agent parses for
the tool description and parameter schema.
"""

import json
import logging
from pathlib import Path

from backend.services import (
    list_jobs,
    get_job,
    get_candidate,
    create_candidate,
    save_parsed_resume,
    get_parsed_resume,
    create_application,
)
from backend.services.resume_parser import parse_resume, parse_resume_from_file, ResumeParseError
from backend.services.email import send_email, EmailSendError
from backend.agent.matching import rank_matches
from backend.agent.prompts import SCREENING_QUESTION_PROMPT, EMAIL_DRAFT_PROMPT
from backend.config import MODEL_REASONING, QWEN_API_KEY, QWEN_BASE_URL

from openai import OpenAI

logger = logging.getLogger(__name__)

# How many questions to generate per tier
TIER_QUESTION_COUNT = {
    "STRONG_MATCH": 2,
    "PARTIAL_MATCH": 3,
    "WEAK_MATCH": 4,
}


def parse_resume_tool(pdf_path: str) -> str:
    """Parse a CV/resume PDF file and extract structured candidate information.

    Args:
        pdf_path: Path to the PDF file on disk.

    Returns:
        JSON string with parsed candidate data (name, email, phone, skills, experiences, education, years_experience).
    """
    try:
        parsed = parse_resume_from_file(pdf_path)
        return json.dumps(parsed, indent=2)
    except (ResumeParseError, FileNotFoundError) as e:
        return json.dumps({"error": str(e)})


def list_jobs_tool() -> str:
    """List all available job openings at the company.

    Returns:
        JSON array of job summaries with id, title, company, and recruiter_email.
    """
    jobs = list_jobs()
    summary = [{"id": j["id"], "title": j["title"], "company": j["company"], "min_years": j["min_years"], "required_skills": [s["name"] for s in j["required_skills"]]} for j in jobs]
    return json.dumps(summary, indent=2)


def match_jobs_tool(candidate_id: str) -> str:
    """Match a candidate against all available jobs and return ranked results.

    Args:
        candidate_id: The candidate's unique identifier.

    Returns:
        JSON array of top-5 job matches with scores, tiers, and reasoning.
    """
    parsed = get_parsed_resume(candidate_id)
    if not parsed:
        return json.dumps({"error": f"No parsed resume found for candidate {candidate_id}. Upload a CV first."})

    jobs = list_jobs()
    if not jobs:
        return json.dumps({"error": "No jobs available."})

    results = rank_matches(parsed, jobs, top_n=5)
    return json.dumps([{
        "job_id": r.job_id,
        "job_title": r.job_title,
        "company": r.company,
        "score": r.score,
        "tier": r.tier.value,
        "required_coverage": r.required_coverage,
        "adjacent_bonus": r.adjacent_bonus,
        "experience_score": r.experience_score,
        "reasoning_score": r.reasoning_score,
        "matched_skills": r.matched_skills,
        "missing_skills": r.missing_skills,
        "reasoning_explanation": r.reasoning_explanation,
    } for r in results], indent=2)


def generate_screening_questions_tool(candidate_id: str, job_id: str, match_tier: str = "PARTIAL_MATCH") -> str:
    """Generate targeted screening questions for a candidate-job pair.
    The number of questions adapts to the match tier: STRONG_MATCH gets 1-2, PARTIAL_MATCH gets 2-3, WEAK_MATCH gets 3-4.

    Args:
        candidate_id: The candidate's unique identifier.
        job_id: The job's unique identifier.
        match_tier: The match tier (STRONG_MATCH, PARTIAL_MATCH, or WEAK_MATCH) to control question count.

    Returns:
        JSON object with 'questions' (list), 'tier', and 'focus_areas' (list).
    """
    parsed = get_parsed_resume(candidate_id)
    job = get_job(job_id)
    if not parsed or not job:
        return json.dumps({"error": "Candidate or job not found."})

    num_questions = TIER_QUESTION_COUNT.get(match_tier, 3)

    if not QWEN_API_KEY:
        # Fallback questions
        fallback = [
            "Tell me about your experience with the key technologies for this role.",
            "Describe a recent project where you used the primary tech stack.",
            "How many years of production experience do you have with the core tools?",
            "What interests you about this specific position?",
        ]
        return json.dumps({
            "questions": fallback[:num_questions],
            "tier": match_tier,
            "focus_areas": ["general fit"],
        }, indent=2)

    client = OpenAI(base_url=QWEN_BASE_URL, api_key=QWEN_API_KEY)
    try:
        # Compute match to identify gaps
        results = rank_matches(parsed, [job], top_n=1)
        gap_info = ""
        if results:
            r = results[0]
            gap_info = f"\nMatch score: {r.score} ({r.tier.value}). Missing skills: {r.missing_skills}. Reasoning: {r.reasoning_explanation}"

        prompt = f"""Generate exactly {num_questions} screening questions for this candidate-job pair.
Match tier: {match_tier} (target {num_questions} questions).

CANDIDATE:
{json.dumps(parsed, indent=2)}

JOB:
{json.dumps(job, indent=2)}{gap_info}

Return as JSON: {{"questions": ["q1", "q2", ...], "tier": "{match_tier}", "focus_areas": ["area1", "area2"]}}"""

        response = client.chat.completions.create(
            model=MODEL_REASONING,
            messages=[
                {"role": "system", "content": SCREENING_QUESTION_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=800,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            import re
            raw = re.sub(r"^```(?:json)?\s*\n?", "", raw)
            raw = re.sub(r"\n?```\s*$", "", raw)
        data = json.loads(raw)
        # Ensure correct structure
        if isinstance(data, list):
            data = {"questions": data, "tier": match_tier, "focus_areas": []}
        data.setdefault("questions", [])
        data.setdefault("tier", match_tier)
        data.setdefault("focus_areas", [])
        return json.dumps(data, indent=2)
    except Exception as e:
        logger.warning("Failed to generate screening questions: %s", e)
        fallback = [
            "Tell me about your experience with the key technologies for this role.",
            "Describe a recent project where you used the primary tech stack.",
            "How many years of production experience do you have?",
            "What interests you about this position?",
        ]
        return json.dumps({
            "questions": fallback[:num_questions],
            "tier": match_tier,
            "focus_areas": ["general fit"],
        }, indent=2)


def confirm_and_draft_email_tool(candidate_id: str, job_id: str, screening_answers: dict) -> str:
    """Draft a professional email to the recruiter for the candidate to review before sending.

    Args:
        candidate_id: The candidate's unique identifier.
        job_id: The job's unique identifier.
        screening_answers: Dict of question -> answer pairs from the screening step.

    Returns:
        JSON object with 'to', 'subject', and 'body' fields for the draft email.
    """
    parsed = get_parsed_resume(candidate_id)
    job = get_job(job_id)
    if not parsed or not job:
        return json.dumps({"error": "Candidate or job not found."})

    if not QWEN_API_KEY:
        return json.dumps({
            "to": job["recruiter_email"],
            "subject": f"Application: {parsed['name']} for {job['title']}",
            "body": f"Dear Recruiter,\n\nI am writing to express my interest in the {job['title']} position at {job['company']}.\n\nBest regards,\n{parsed['name']}"
        })

    client = OpenAI(base_url=QWEN_BASE_URL, api_key=QWEN_API_KEY)
    try:
        response = client.chat.completions.create(
            model=MODEL_REASONING,
            messages=[
                {"role": "system", "content": EMAIL_DRAFT_PROMPT},
                {"role": "user", "content": f"CANDIDATE:\n{json.dumps(parsed, indent=2)}\n\nJOB:\n{json.dumps(job, indent=2)}\n\nSCREENING ANSWERS:\n{json.dumps(screening_answers, indent=2)}\n\nRecruiter email: {job['recruiter_email']}"},
            ],
            temperature=0.3,
            max_tokens=800,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            import re
            raw = re.sub(r"^```(?:json)?\s*\n?", "", raw)
            raw = re.sub(r"\n?```\s*$", "", raw)
        draft = json.loads(raw)
        draft.setdefault("to", job["recruiter_email"])
        return json.dumps(draft, indent=2)
    except Exception as e:
        logger.warning("Failed to draft email: %s", e)
        return json.dumps({
            "to": job["recruiter_email"],
            "subject": f"Application: {parsed['name']} for {job['title']}",
            "body": f"Dear Recruiter,\n\nI am writing to express my interest in the {job['title']} position at {job['company']}.\n\nBest regards,\n{parsed['name']}"
        })


def send_email_tool(to: str, subject: str, body: str, candidate_id: str) -> str:
    """Send a draft email to the recruiter via DirectMail.

    Args:
        to: Recipient email address.
        subject: Email subject.
        body: Email body text.
        candidate_id: The candidate's ID for audit logging.

    Returns:
        JSON with status and message_id on success, or error on failure.
    """
    try:
        message_id = send_email(to=to, subject=subject, body=body, candidate_id=candidate_id)
        return json.dumps({"status": "sent", "message_id": message_id})
    except EmailSendError as e:
        return json.dumps({"status": "failed", "error": str(e)})


# Tool registry for the orchestrator
TOOLS = [
    parse_resume_tool,
    list_jobs_tool,
    match_jobs_tool,
    generate_screening_questions_tool,
    confirm_and_draft_email_tool,
    send_email_tool,
]
