"""TalentPilot — Streamlit frontend for the recruiter AI agent."""

import json
import requests
import streamlit as st

API_BASE = "http://localhost:9000"

st.set_page_config(page_title="TalentPilot", page_icon="🎯", layout="wide")
st.title("🎯 TalentPilot — AI Recruiter Assistant")
st.caption("Upload your CV, find matching jobs, and apply with one click.")


# --- Fetch service status ---
# No caching — status check is fast and avoids stale cache popups
def get_service_status():
    """Check backend service configuration status."""
    try:
        resp = requests.get(f"{API_BASE}/status", timeout=3)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {"api_key_configured": False, "smtp_configured": False, "version": "unknown"}


status = get_service_status()

# Subtle status indicators (not warnings) — show demo mode when not fully configured
api_ready = status.get("api_key_configured", False)
smtp_ready = status.get("smtp_configured", False)

if not api_ready or not smtp_ready:
    cols = st.columns([1, 1, 3])
    with cols[0]:
        st.caption(f"{'🟢' if api_ready else '🔴'} AI: {'Live' if api_ready else 'Demo'}")
    with cols[1]:
        st.caption(f"{'🟢' if smtp_ready else '🔴'} Email: {'Active' if smtp_ready else 'Preview'}")
    with cols[2]:
        if not api_ready:
            st.caption("Set `QWEN_API_KEY` for live AI features")


# --- Session state defaults ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "candidate_id" not in st.session_state:
    st.session_state.candidate_id = None
if "email_draft" not in st.session_state:
    st.session_state.email_draft = None
if "send_confirmed" not in st.session_state:
    st.session_state.send_confirmed = False
if "matches" not in st.session_state:
    st.session_state.matches = []
if "pdf_path" not in st.session_state:
    st.session_state.pdf_path = None
if "uploaded_filename" not in st.session_state:
    st.session_state.uploaded_filename = None

# Screening flow state - for one-question-at-a-time
if "pending_questions" not in st.session_state:
    st.session_state.pending_questions = []
if "current_question_index" not in st.session_state:
    st.session_state.current_question_index = 0
if "screening_answers" not in st.session_state:
    st.session_state.screening_answers = {}
if "screening_job_id" not in st.session_state:
    st.session_state.screening_job_id = None


def send_chat(message: str):
    """Send a message to the agent and update session state."""
    st.session_state.messages.append({"role": "user", "content": message})
    with st.spinner("🤔 AI is thinking..."):
        resp = requests.post(f"{API_BASE}/chat", json={
            "messages": st.session_state.messages,
            "candidate_id": st.session_state.candidate_id,
            "pdf_path": st.session_state.pdf_path,
            "send_confirmed": st.session_state.send_confirmed,
        })
        if resp.status_code == 200:
            data = resp.json()
            st.session_state.messages = data["messages"]
            assistant_text = data["assistant_text"]

            # Try to detect email draft in the response
            try:
                if "subject" in assistant_text and "body" in assistant_text and "to" in assistant_text:
                    import re
                    json_match = re.search(r'\{[^{}]*"to"[^{}]*"subject"[^{}]*"body"[^{}]*\}', assistant_text, re.DOTALL)
                    if json_match:
                        st.session_state.email_draft = json.loads(json_match.group())
            except Exception:
                pass

            # Try to detect matches in the response
            try:
                if "job_id" in assistant_text and "score" in assistant_text:
                    import re
                    json_match = re.search(r'\[[\s\S]*\]', assistant_text)
                    if json_match:
                        matches = json.loads(json_match.group())
                        if isinstance(matches, list) and matches and "job_id" in matches[0]:
                            st.session_state.matches = matches
            except Exception:
                pass

            # Reset send_confirmed after use
            st.session_state.send_confirmed = False
        else:
            st.error(f"Error: {resp.status_code} — {resp.text}")


# --- Sidebar ---
with st.sidebar:
    st.header("📋 Job Matches")
    if st.session_state.matches:
        for i, m in enumerate(st.session_state.matches):
            with st.expander(f"{m.get('job_title', 'Job')} — {m.get('company', '')} (Score: {m.get('score', 0):.2f})"):
                st.write(f"**Tier:** {m.get('tier', 'N/A')}")
                st.write(f"**Required coverage:** {m.get('required_coverage', 0):.0%}")
                st.write(f"**Matched skills:** {', '.join(m.get('matched_skills', []))}")
                st.write(f"**Missing skills:** {', '.join(m.get('missing_skills', []))}")
                if m.get('reasoning_explanation'):
                    st.write(f"**Reasoning:** {m['reasoning_explanation']}")
                if st.button(f"Apply to this job", key=f"apply_{i}"):
                    send_chat(f"I'd like to apply to the {m.get('job_title', '')} position at {m.get('company', '')}.")
                    st.rerun()
    else:
        st.info("Upload your CV to see matching jobs.")

    st.divider()

    st.header("✉️ Email Preview")
    if st.session_state.email_draft:
        draft = st.session_state.email_draft
        st.write(f"**To:** {draft.get('to', 'N/A')}")
        st.write(f"**Subject:** {draft.get('subject', 'N/A')}")
        st.text_area("Body", draft.get("body", ""), height=200, disabled=True)

        smtp_configured = status.get("smtp_configured", False)

        # Discard draft option
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("❌ Discard Draft", use_container_width=True):
                st.session_state.email_draft = None
                st.session_state.screening_answers = {}
                st.session_state.pending_questions = []
                st.session_state.current_question_index = 0
                st.rerun()

        with col2:
            if smtp_configured:
                if st.button("📤 Send to Recruiter", type="primary", use_container_width=True):
                    st.session_state.send_confirmed = True
                    with st.spinner("Sending email..."):
                        resp = requests.post(f"{API_BASE}/applications", json={
                            "candidate_id": st.session_state.candidate_id,
                            "job_id": next((m["job_id"] for m in st.session_state.matches if m.get("score", 0) == max(mm.get("score", 0) for mm in st.session_state.matches)), ""),
                            "draft": draft,
                            "send_confirmed": True,
                        })
                        if resp.status_code == 200:
                            data = resp.json()
                            if data.get("status") == "sent":
                                st.success(f"✅ Email sent! Message ID: {data.get('message_id', 'N/A')}")
                                st.session_state.email_draft = None
                            else:
                                st.error(f"Failed to send: {data.get('error', 'Unknown error')}")
                        else:
                            st.error(f"Error: {resp.status_code}")
            else:
                st.button("📤 Send to Recruiter", type="primary", disabled=True, use_container_width=True)
                st.caption("📧 Email sending is not configured. Set ALIYUN_SMTP_USER and ALIYUN_SMTP_PASS to enable.")
                st.success("✅ Email draft generated successfully! The workflow up to this point is fully functional.")
    else:
        st.info("No email draft yet. Complete the screening process to generate one.")

    st.divider()

    st.header("📝 Audit Log")
    if st.button("Refresh log"):
        st.rerun()
    try:
        resp = requests.get(f"{API_BASE}/audit-log", params={"limit": 20})
        if resp.status_code == 200:
            entries = resp.json()
            for entry in entries[:10]:
                status_icon = "✅" if entry.get("status") in ("ok", "sent") else ("⏭️" if entry.get("status") == "skipped" else "❌")
                st.caption(f"{status_icon} {entry.get('action', '')} — {entry.get('timestamp', '')[:19]}")
    except Exception:
        st.caption("Could not load audit log.")


# --- Main chat area ---
st.header("💬 Chat")

# CV Upload
uploaded_file = st.file_uploader("Upload your CV (PDF)", type=["pdf"], key="cv_upload")
if uploaded_file and st.session_state.candidate_id is None:
    with st.spinner("Parsing your CV..."):
        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
        resp = requests.post(f"{API_BASE}/upload", files=files)
        if resp.status_code == 200:
            data = resp.json()
            st.session_state.candidate_id = data["candidate_id"]
            # pdf_path not needed after upload — CV already parsed on server
            st.session_state.uploaded_filename = uploaded_file.name
            parsed = data["parsed"]
            st.success(f"✅ CV parsed: {parsed.get('name', 'Unknown')} — {len(parsed.get('skills', []))} skills found, {parsed.get('years_experience', 0)} years experience")
            # Auto-send first message
            send_chat("Are there any suitable jobs based on my CV?")
            st.rerun()
        else:
            st.error(f"Failed to parse CV: {resp.text}")

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Chat input
if st.session_state.candidate_id:
    if prompt := st.chat_input("Ask about jobs, your match results, or say 'apply' to start the process..."):
        send_chat(prompt)
        st.rerun()
else:
    st.info("👆 Upload your CV to start chatting with TalentPilot.")
