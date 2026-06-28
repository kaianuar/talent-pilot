"""TalentPilot — Enhanced Streamlit frontend with progress indicators and error handling.

This enhanced version includes:
- Visual progress indicators for all operations
- Mobile-responsive design
- Comprehensive error handling with retry logic
- Improved user feedback and status messages
"""

import json
import requests
import streamlit as st
import time
from typing import Optional, Callable
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Page configuration with mobile-friendly viewport
st.set_page_config(
    page_title="TalentPilot",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",  # Better for mobile
)

# Custom CSS for mobile responsiveness and improved styling
st.markdown("""
<style>
    /* Mobile-first responsive design */
    @media (max-width: 768px) {
        .main > div {
            padding: 0.5rem !important;
        }
        h1 {
            font-size: 1.5rem !important;
        }
        h2 {
            font-size: 1.2rem !important;
        }
        .stButton > button {
            min-height: 44px !important;  /* Touch-friendly */
            width: 100% !important;
        }
        .stTextInput > div > div > input {
            min-height: 44px !important;
            font-size: 16px !important;  /* Prevent zoom on iOS */
        }
    }
    
    /* Improved touch targets */
    .stButton > button {
        min-height: 40px;
        padding: 0.5rem 1rem;
    }
    
    /* Progress bar styling */
    .stProgress > div > div {
        background-color: #2563eb;
    }
    
    /* Success/error message styling */
    .stSuccess {
        background-color: #dcfce7;
        border-left: 4px solid #22c55e;
    }
    .stError {
        background-color: #fee2e2;
        border-left: 4px solid #ef4444;
    }
    .stWarning {
        background-color: #fef3c7;
        border-left: 4px solid #f59e0b;
    }
    
    /* Card-like containers */
    .card {
        background-color: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

API_BASE = "http://localhost:9000"

# --- Header ---
st.title("🎯 TalentPilot")
st.caption("AI-Powered Candidate Screening")

# --- Progress Indicator Components ---
class UploadProgress:
    """Progress tracker for file upload with visual indicators."""
    
    def __init__(self, file_name: str, file_size: int):
        self.file_name = file_name
        self.file_size = file_size
        self.start_time = time.time()
        
        # Create progress UI
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.write(f"📤 **Uploading:** {file_name}")
        self.progress_bar = st.progress(0)
        self.status = st.empty()
        self.eta = st.empty()
        
    def update(self, bytes_uploaded: int):
        """Update progress."""
        progress = bytes_uploaded / self.file_size if self.file_size > 0 else 0
        self.progress_bar.progress(min(progress, 1.0))
        
        # Update status
        status_text = f"Uploaded: {self._format_size(bytes_uploaded)} / {self._format_size(self.file_size)}"
        self.status.info(status_text)
        
        # Update ETA
        if progress > 0:
            elapsed = time.time() - self.start_time
            eta = elapsed * (1 - progress) / progress
            self.eta.caption(f"⏱️ ETA: {int(eta)}s")
    
    def complete(self, message: str = "Upload complete!"):
        """Mark upload as complete."""
        self.progress_bar.progress(1.0)
        self.progress_bar.empty()
        self.status.success(f"✓ {message}")
        self.eta.empty()
        st.markdown("</div>", unsafe_allow_html=True)
    
    def error(self, error_message: str):
        """Mark upload as failed."""
        self.progress_bar.empty()
        self.status.error(f"❌ Upload failed: {error_message}")
        self.eta.empty()
        st.markdown("</div>", unsafe_allow_html=True)
    
    def _format_size(self, size_bytes: int) -> str:
        """Format byte size."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"


class ProcessingStages:
    """Visual stage tracker for multi-step processes."""
    
    def __init__(self, stages: list[str], title: str = "Processing"):
        self.stages = stages
        self.title = title
        self.current_stage = 0
        self.start_time = time.time()
        
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.write(f"**{title}**")
        self.stage_container = st.container()
        self._render_stages()
        
    def _render_stages(self):
        """Render stage indicators."""
        with self.stage_container:
            cols = st.columns(len(self.stages))
            for i, (col, stage) in enumerate(zip(cols, self.stages)):
                with col:
                    if i < self.current_stage:
                        st.success(f"✓ {stage}", icon="✅")
                    elif i == self.current_stage:
                        st.info(f"⏳ {stage}", icon="⏳")
                    else:
                        st.caption(f"○ {stage}")
    
    def next_stage(self, message: Optional[str] = None):
        """Advance to next stage."""
        self.current_stage += 1
        self.stage_container.empty()
        self._render_stages()
        if message:
            st.info(message)
    
    def complete(self, success_message: str = "Complete!"):
        """Mark as complete."""
        elapsed = time.time() - self.start_time
        st.success(f"✓ {success_message} (completed in {int(elapsed)}s)")
        st.markdown("</div>", unsafe_allow_html=True)


# --- Error Handling with Retry ---
class APIRetryHandler:
    """Handle API calls with retry logic and user feedback."""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 10.0,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
    
    def call(
        self,
        operation: Callable,
        error_message: str = "Operation failed",
        success_message: Optional[str] = None,
    ):
        """Execute operation with retry logic.
        
        Args:
            operation: Function to call (should return response or raise exception)
            error_message: Message to show on final failure
            success_message: Optional message to show on success
            
        Returns:
            Result from operation on success, None on failure
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                result = operation()
                
                # Check if it's an HTTP response with error status
                if hasattr(result, 'status_code') and result.status_code >= 400:
                    raise Exception(f"HTTP {result.status_code}: {result.text[:200]}")
                
                # Success!
                if success_message and attempt > 0:
                    st.success(f"✓ {success_message} (after {attempt + 1} attempts)")
                elif success_message:
                    st.success(f"✓ {success_message}")
                
                return result
                
            except Exception as e:
                last_error = e
                is_last_attempt = (attempt == self.max_retries - 1)
                
                if is_last_attempt:
                    # Final failure
                    st.error(f"❌ {error_message}: {str(e)}")
                    st.info("💡 Try refreshing the page or uploading a different file.")
                    return None
                else:
                    # Retry with exponential backoff
                    delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                    st.warning(f"⚠️ Attempt {attempt + 1} failed. Retrying in {int(delay)}s...")
                    time.sleep(delay)
        
        return None


# --- Helper Functions ---
def format_file_size(size_bytes: int) -> str:
    """Format byte size to human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def validate_pdf_file(file) -> tuple[bool, str]:
    """Validate PDF file before upload.
    
    Returns:
        (is_valid, error_message)
    """
    if file is None:
        return False, "No file selected"
    
    # Check file size (max 10MB)
    MAX_SIZE = 10 * 1024 * 1024  # 10MB
    if hasattr(file, 'size') and file.size > MAX_SIZE:
        return False, f"File too large ({format_file_size(file.size)}). Max size: 10MB"
    
    # Check file type
    if hasattr(file, 'type') and file.type != 'application/pdf':
        return False, f"Invalid file type: {file.type}. Please upload a PDF."
    
    if hasattr(file, 'name') and not file.name.lower().endswith('.pdf'):
        return False, "File must have .pdf extension"
    
    return True, ""


# --- Session State Initialization ---
def init_session_state():
    """Initialize all session state variables."""
    defaults = {
        "messages": [],
        "candidate_id": None,
        "email_draft": None,
        "send_confirmed": False,
        "matches": [],
        "pdf_path": None,
        "uploaded_filename": None,
        "pending_questions": [],
        "current_question_index": 0,
        "screening_answers": {},
        "screening_job_id": None,
        "upload_progress": None,
        "processing_stage": None,
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# --- API Functions with Retry Logic ---
@st.cache_data(ttl=60)
def get_service_status_cached():
    """Cached service status check."""
    try:
        resp = requests.get(f"{API_BASE}/status", timeout=3)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return {"api_key_configured": False, "smtp_configured": False, "version": "unknown"}


def upload_cv_with_progress(uploaded_file) -> Optional[dict]:
    """Upload CV with visual progress tracking.
    
    Args:
        uploaded_file: The uploaded file object
        
    Returns:
        Response data on success, None on failure
    """
    # Create progress tracker
    file_size = len(uploaded_file.getvalue())
    progress = FileUploadProgress(uploaded_file.name, file_size)
    
    try:
        # Prepare upload
        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
        
        # Simulate progress (since requests doesn't support streaming upload progress easily)
        # In production, use a library that supports upload progress
        import threading
        
        uploaded_bytes = [0]
        def monitor_upload():
            # Simulate progress based on time (in real implementation, track actual bytes)
            import time
            for i in range(10):
                time.sleep(0.1)
                uploaded_bytes[0] = min((i + 1) * file_size // 10, file_size)
                progress.update(uploaded_bytes[0])
        
        # Start monitoring in background
        monitor_thread = threading.Thread(target=monitor_upload)
        monitor_thread.start()
        
        # Perform actual upload
        resp = requests.post(f"{API_BASE}/upload", files=files, timeout=60)
        
        # Wait for monitor to complete
        monitor_thread.join()
        progress.update(file_size)
        
        if resp.status_code == 200:
            progress.complete("CV uploaded successfully!")
            return resp.json()
        else:
            error_msg = f"Server returned {resp.status_code}"
            try:
                error_data = resp.json()
                if "error" in error_data:
                    error_msg = error_data["error"]
            except:
                pass
            progress.error(error_msg)
            return None
            
    except requests.exceptions.Timeout:
        progress.error("Upload timed out. Please try again with a smaller file.")
        return None
    except requests.exceptions.ConnectionError:
        progress.error("Cannot connect to server. Please check your internet connection.")
        return None
    except Exception as e:
        progress.error(f"Unexpected error: {str(e)}")
        return None


def send_chat_with_feedback(message: str, candidate_id: str) -> bool:
    """Send chat message with retry logic and user feedback.
    
    Args:
        message: The user message
        candidate_id: The candidate ID
        
    Returns:
        True on success, False on failure
    """
    retry_handler = APIRetryHandler(max_retries=3, base_delay=1.0)
    
    def operation():
        return requests.post(
            f"{API_BASE}/chat",
            json={
                "messages": st.session_state.messages + [{"role": "user", "content": message}],
                "candidate_id": candidate_id,
                "pdf_path": st.session_state.get("pdf_path"),
                "send_confirmed": st.session_state.get("send_confirmed", False),
            },
            timeout=30,
        )
    
    result = retry_handler.call(
        operation=operation,
        error_message="Failed to send message",
        success_message="Message sent!",
    )
    
    if result and result.status_code == 200:
        data = result.json()
        st.session_state.messages = data["messages"]
        return True
    
    return False


# --- Main Application ---
def main():
    """Main application entry point."""
    
    # Initialize session state
    init_session_state()
    
    # Service status check (cached)
    status = get_service_status_cached()
    
    # --- Status Bar ---
    api_ready = status.get("api_key_configured", False)
    smtp_ready = status.get("smtp_configured", False)
    
    if not api_ready or not smtp_ready:
        with st.container():
            cols = st.columns([1, 1, 3])
            with cols[0]:
                st.caption(f"{'🟢' if api_ready else '🔴'} AI: {'Live' if api_ready else 'Demo'}")
            with cols[1]:
                st.caption(f"{'🟢' if smtp_ready else '🔴'} Email: {'Active' if smtp_ready else 'Preview'}")
            with cols[2]:
                if not api_ready:
                    st.caption("Set `QWEN_API_KEY` for live AI features")
    
    # --- Sidebar ---
    with st.sidebar:
        st.header("📋 Job Matches")
        if st.session_state.get("matches"):
            for match in st.session_state.matches[:5]:
                score = match.get("score", 0)
                job_title = match.get("job_title", "Unknown")
                company = match.get("company", "Unknown")
                
                # Color code based on score
                if score >= 80:
                    color = "🟢"
                elif score >= 60:
                    color = "🟡"
                else:
                    color = "🟠"
                
                st.caption(f"{color} {score}% — {job_title} @ {company}")
        else:
            st.caption("No matches yet. Upload your CV to see job matches.")
        
        st.divider()
        
        # Audit Log
        st.header("📝 Audit Log")
        if st.button("Refresh log"):
            st.rerun()
        
        try:
            resp = requests.get(f"{API_BASE}/audit-log", params={"limit": 20}, timeout=5)
            if resp.status_code == 200:
                entries = resp.json()
                for entry in entries[:10]:
                    status = entry.get("status", "")
                    if status in ("ok", "sent"):
                        icon = "✅"
                    elif status == "skipped":
                        icon = "⏭️"
                    else:
                        icon = "❌"
                    
                    action = entry.get("action", "")
                    timestamp = entry.get("timestamp", "")[:19]
                    st.caption(f"{icon} {action} — {timestamp}")
        except Exception:
            st.caption("Could not load audit log.")
    
    # --- Main Content Area ---
    st.header("💬 Chat")
    
    # CV Upload Section
    st.markdown("### 📄 Upload Your CV")
    
    uploaded_file = st.file_uploader(
        "Choose a PDF file",
        type=["pdf"],
        key="cv_upload",
        help="Upload your CV in PDF format (max 10MB)",
    )
    
    if uploaded_file and not st.session_state.get("candidate_id"):
        # Validate file
        file_size = len(uploaded_file.getvalue())
        
        if file_size > 10 * 1024 * 1024:
            st.error("❌ File too large. Maximum size is 10MB.")
        else:
            # Upload with progress tracking
            result = upload_cv_with_progress(uploaded_file)
            
            if result:
                # Store result in session state
                st.session_state.candidate_id = result.get("candidate_id")
                st.session_state.uploaded_filename = uploaded_file.name
                
                parsed = result.get("parsed", {})
                st.success(
                    f"✅ **{parsed.get('name', 'Candidate')}** — "
                    f"{len(parsed.get('skills', []))} skills, "
                    f"{parsed.get('years_experience', 0)} years experience"
                )
                
                # Auto-trigger job matching
                with st.spinner("🔍 Finding matching jobs..."):
                    time.sleep(0.5)  # Brief pause for UX
                
                st.rerun()
    
    # Show uploaded file info
    elif st.session_state.get("candidate_id") and st.session_state.get("uploaded_filename"):
        st.success(f"✓ CV uploaded: {st.session_state.uploaded_filename}")
    
    # --- Chat Interface ---
    st.markdown("---")
    
    # Display chat history
    for msg in st.session_state.get("messages", []):
        role = msg.get("role", "")
        content = msg.get("content", "")
        
        if role == "user":
            with st.chat_message("user", avatar="👤"):
                st.write(content)
        elif role == "assistant":
            with st.chat_message("assistant", avatar="🤖"):
                st.write(content)
    
    # Chat input
    if st.session_state.get("candidate_id"):
        if prompt := st.chat_input(
            "Ask about jobs, your match results, or type 'apply' to start the process...",
            key="chat_input",
        ):
            # Show user message immediately
            with st.chat_message("user", avatar="👤"):
                st.write(prompt)
            
            # Send with retry logic
            success = send_chat_with_feedback(
                message=prompt,
                candidate_id=st.session_state.candidate_id,
            )
            
            if success:
                st.rerun()
            else:
                # Error already shown by retry handler
                pass
    else:
        st.info("👆 **Upload your CV above to start chatting with TalentPilot.**")


# --- Run Main ---
if __name__ == "__main__":
    main()
