# Demo video script (~3 minutes)

Target length: **2:45 – 3:15**. Keep it tight; the judging panel watches
dozens of these.

## Setup (before recording)

- Use the **live deployment URL** from the runbook, not localhost. Judges
  want to see the actual cloud URL.
- Open Chrome dev tools on the right side of the screen (Network tab, no
  throttling). This shows that the LLM calls are real and that responses
  take real time.
- A sample resume PDF ready to drag into the upload area. Use a real
  resume — fake ones look fake.
- Pre-warm the deployment: do one full upload + match + screening flow
  60 seconds before recording. First-call cold starts are slow and
  eat time in a 3-minute window.
- Close unrelated tabs. Clear the console.

## Shot list

### 0:00 – 0:20 — Intro (the problem)

Screen: title card or the empty app with a voiceover.

> "TalentPilot is an AI recruiter agent built for Track 4: Autopilot Agent.
> The problem: recruiters spend 70% of their time screening candidates
> against job descriptions. TalentPilot takes a candidate from CV upload
> to a recruiter-ready email in one autonomous flow — with a human-in-
> the-loop gate before any email leaves the system."

(Keep this tight. Show the empty app for a few seconds while you talk.)

### 0:20 – 1:00 — CV upload + parsing (live)

Action: drag the sample PDF into the upload zone.

Voiceover while the spinner shows:
> "The candidate drops in a CV. The parser — running qwen-turbo for
> text-extractable PDFs and qwen3-vl-plus as a fallback for scanned
> ones — extracts the candidate's name, email, skills, and years of
> experience. Parsed data backfills the candidate row in the database."

When the profile card appears, point out the parsed fields. Confirm
they match the PDF. **Don't name every field; pick one or two.**

### 1:00 – 1:40 — Matching (live)

Action: click "Match" (or however the UI is wired).

Voiceover:
> "The match endpoint scores the candidate against all 32 jobs in
> the seed dataset. It combines skill coverage, adjacent-skill bonus,
> experience relative to the job's minimum, and a reasoning score
> from qwen3-max. The reasoning score is cached per (candidate, job,
> resume-hash) — re-running this returns the same scores, no
> non-determinism."

Show the job cards. Pick the top one and **say why** it scored well
(be specific about the skill match). Note the tier label.

### 1:40 – 2:20 — Screening (live)

Action: click "Start Screening" on the top match.

Voiceover:
> "Screening is driven by a LangGraph state machine. qwen3-max reads
> the candidate's resume, identifies skill gaps, and generates a
> targeted question. The candidate answers; qwen3-max assesses the
> answer's quality. Two good answers and the session is done."

Answer 2-3 questions with reasonable responses. The system asks; you
answer. Real-time WebSocket progress bar advances.

At session end, show the screening result screen with:
- Final status (Passed / Failed)
- The drafted email (show, don't read it)
- The "Send to Recruiter" button (visible but not clicked yet)

Voiceover:
> "The session ends with a drafted recruiter email and a HITL gate.
> The email is **not** sent. The candidate reviews the draft and
> confirms with one click. Until they confirm, no email leaves the
> system — that's the two-layer defense we built into both the API
> and the UI."

### 2:20 – 2:50 — The HITL moment (live)

Action: click "Send to Recruiter".

Voiceover:
> "The candidate confirms. The API receives `send_confirmed=True`,
> the SMTP service sends the email via Alibaba DirectMail, and an
> audit log entry is created. The chat panel announces the send
> to the candidate."

Show the audit log briefly. Then briefly show:
- A different browser tab / request to `/audit-log?candidate_id=...`
  to show the entry.

> "Every action — uploads, matches, screenings, sends — is auditable.
> The candidate has the final word, the audit log has the receipt."

### 2:50 – 3:00 — Architecture one-liner (optional but recommended)

Screen: switch to the architecture diagram (`docs/architecture.mmd`
rendered as PNG) for 10 seconds.

Voiceover:
> "Hexagonal architecture: domain logic in `backend/domain/`,
  application use cases in `backend/application/`, infrastructure
  adapters in `backend/infrastructure/`. LangGraph orchestrates the
  screening flow. gRPC streaming for real-time questions, WebSocket
  for progress, REST for everything else."

### 3:00 – 3:15 — Outro

Screen: the app, idle.

> "TalentPilot. CV to recruiter email, with the candidate in control.
> Built on Qwen Cloud, deployed on Alibaba Cloud, source on GitHub.
> Track 4: Autopilot Agent."

Fade to black. End.

## What to NOT do

- **Don't read the email aloud.** It's the one thing in the demo that
  has nothing to prove — just show it.
- **Don't explain the score formula in detail.** "combines skill
  coverage, experience, and LLM reasoning" is enough. The diagram
  covers the rest.
- **Don't apologize for slow responses.** First cold-start takes a
  beat. Pre-warm so the demo doesn't hit a 30-second parse.
- **Don't show a fake upload.** Use a real PDF. The judge will notice
  if "Name" and "Email" are perfect-looking fakes.

## Tech notes for editing

- Use Loom, Screen Studio, or OBS. 1080p is fine.
- Add 1-second pause cuts at the section boundaries — your recorded
  pauses will be too long otherwise.
- Closed captions help, especially for the "LLM" / "qwen3-max" / "ACS"
  terms. Let the auto-caption generator take a first pass, then fix
  the model names manually.
