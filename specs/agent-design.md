# Agent Design Spec

## Overview
The agent orchestrates the full screening workflow using a tool-calling loop with qwen3-max. It follows the OpenAI-compatible function calling protocol.

## Agent Configuration

**Model**: qwen3-max (DashScope International)
**Temperature**: 0.3 (balanced creativity/determinism)
**Max tool rounds**: 10 (prevents infinite loops)

## System Prompt

```
You are TalentPilot, an AI recruiter assistant for RecruiterCo.

Your job is to help candidates find suitable jobs by:
1. Parsing their uploaded CV/resume
2. Matching it against the company's job listings
3. Asking 2-3 targeted screening questions for promising matches
4. Drafting a professional email to the recruiter when the candidate wants to apply
5. NEVER sending the email without explicit human confirmation

Rules:
- Always use tools to get real data — never guess job IDs, recruiter emails, or match scores.
- If no jobs match well, say so honestly and suggest the candidate broaden their search.
- When asking screening questions, focus on gaps identified in the match.
- Keep responses concise and professional.
- NEVER call send_email_tool unless the candidate has explicitly confirmed after seeing the draft.
```

## MCP-Style Tools (6 total)

### 1. `parse_resume_tool`
**Purpose**: Extract structured data from a CV PDF.
**Input**: `pdf_path` (string)
**Output**: JSON with name, email, phone, skills, experiences, education, years_experience
**Backend**: `services.resume_parser.parse_resume()` → Qwen3-VL-Plus

### 2. `list_jobs_tool`
**Purpose**: List all available job openings.
**Input**: None
**Output**: JSON array of `{id, title, company, min_years, required_skills}`
**Backend**: `services.jobs.list_jobs()`

### 3. `match_jobs_tool`
**Purpose**: Match a candidate against all jobs, return ranked results.
**Input**: `candidate_id` (string)
**Output**: JSON array of top-5 matches with scores, tiers, reasoning
**Backend**: `matching.rank_matches()`

### 4. `generate_screening_questions_tool`
**Purpose**: Generate targeted questions for a candidate-job pair.
**Input**: `candidate_id`, `job_id`
**Output**: JSON array of 2-3 question strings
**Backend**: qwen3-max with gap-focused prompt

### 5. `confirm_and_draft_email_tool`
**Purpose**: Draft a recruiter email for human review.
**Input**: `candidate_id`, `job_id`, `screening_answers` (dict)
**Output**: JSON `{to, subject, body}`
**Backend**: qwen3-max with email drafting prompt
**Note**: Does NOT send the email — draft only.

### 6. `send_email_tool`
**Purpose**: Send a draft email via DirectMail.
**Input**: `to`, `subject`, `body`, `candidate_id`
**Output**: JSON `{status, message_id}` or `{status, error}`
**Backend**: `services.email.send_email()`
**Guard**: Blocked unless `send_confirmed=True`

## Orchestrator Loop

```python
def run_turn(messages, candidate_id, pdf_path=None, send_confirmed=False):
    # 1. Build message list with system prompt
    # 2. Loop up to max_tool_rounds:
    #    a. Call LLM with tools
    #    b. If no tool calls → return text response
    #    c. For each tool call:
    #       - If send_email_tool and not send_confirmed → block
    #       - Execute tool
    #       - Append result to messages
    #    d. Continue loop
    # 3. Return updated messages + assistant text
```

## Human-in-the-Loop Enforcement

Triple-layer defense:

### Layer 1: System Prompt
```
NEVER call send_email_tool unless the candidate has explicitly clicked 'Send' on a drafted email in the previous turn.
```

### Layer 2: Orchestrator Code
```python
if name == "send_email_tool" and not send_confirmed:
    return {"status": "blocked", "message": "I need your confirmation..."}
```

### Layer 3: API Endpoint
```python
@app.post("/applications")
async def submit_application(req: ApplicationRequest):
    if not req.send_confirmed:
        raise HTTPException(403, "send_confirmed must be True")
```

### Layer 4: Frontend
```python
# Only the "Send to Recruiter" button sets this
if st.button("Send to Recruiter"):
    st.session_state.send_confirmed = True
```

## Conversation Flow

### Happy Path
```
User: [uploads CV]
Agent: [calls parse_resume_tool] → "I found 6 skills and 6 years of experience."
Agent: [auto-triggered] "Are there any suitable jobs based on my CV?"

User: "Yes, show me matches"
Agent: [calls match_jobs_tool] → "Here are your top 5 matches..."

User: "Apply to the top one"
Agent: [calls generate_screening_questions_tool] → "Before I draft the email, I have 3 questions..."

User: [answers questions]
Agent: [calls confirm_and_draft_email_tool] → "Here's the draft email. Click Send when ready."

User: [clicks Send button]
Agent: [calls send_email_tool] → "Email sent! Message ID: abc123"
```

### Rejection Path
```
User: [uploads CV with no matching skills]
Agent: [calls match_jobs_tool] → "Unfortunately, no jobs match your current skill set well."
Agent: "Consider developing skills in X, Y, Z to improve your match."
```

### Ambiguous Input Path
```
User: [uploads CV with vague titles]
Agent: [calls parse_resume_tool] → "I see you have experience, but could you clarify..."
Agent: "What specific technologies did you use in your last role?"
```

## Tool Definitions (OpenAI Format)

Each tool is defined as:
```json
{
  "type": "function",
  "function": {
    "name": "tool_name",
    "description": "What the tool does",
    "parameters": {
      "type": "object",
      "properties": { ... },
      "required": [...]
    }
  }
}
```

## Error Handling

- **Tool failure**: Returns error JSON, agent sees it and communicates to user
- **LLM failure**: Returns user-friendly error, logs to audit
- **Infinite loop**: Max 10 tool rounds forces a text response
- **Malformed tool args**: JSON parse failure → empty dict, tool handles gracefully
