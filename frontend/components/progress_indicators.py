"""Progress indicator components for TalentPilot.

This module provides enhanced progress indicators for long-running operations
like file uploads, CV parsing, and AI processing.
"""

import time
from typing import Optional, Callable
import streamlit as st


class ProgressTracker:
    """Track progress of multi-stage operations with visual indicators."""
    
    def __init__(
        self,
        stages: list[str],
        title: str = "Processing",
        show_eta: bool = True,
    ):
        """Initialize progress tracker.
        
        Args:
            stages: List of stage names (e.g., ["Uploading", "Parsing", "Analyzing"])
            title: Title to display above progress bar
            show_eta: Whether to show estimated time remaining
        """
        self.stages = stages
        self.title = title
        self.show_eta = show_eta
        self.current_stage = 0
        self.start_time = time.time()
        
        # Create Streamlit components
        self._create_components()
    
    def _create_components(self):
        """Create Streamlit progress components."""
        st.subheader(self.title)
        
        # Progress bar
        self.progress_bar = st.progress(0)
        
        # Status text
        self.status_text = st.empty()
        
        # ETA text
        if self.show_eta:
            self.eta_text = st.empty()
        
        # Stage indicators
        self._render_stage_indicators()
    
    def _render_stage_indicators(self):
        """Render visual stage indicators."""
        cols = st.columns(len(self.stages))
        
        for i, (col, stage) in enumerate(zip(cols, self.stages)):
            with col:
                if i < self.current_stage:
                    # Completed stage
                    st.success(f"✓ {stage}")
                elif i == self.current_stage:
                    # Current stage
                    st.info(f"⏳ {stage}")
                else:
                    # Future stage
                    st.caption(f"○ {stage}")
    
    def update_progress(self, progress: float, status_message: Optional[str] = None):
        """Update progress bar.
        
        Args:
            progress: Progress value between 0.0 and 1.0
            status_message: Optional status message to display
        """
        # Clamp progress to valid range
        progress = max(0.0, min(1.0, progress))
        
        # Update progress bar
        self.progress_bar.progress(progress)
        
        # Update status text
        if status_message:
            self.status_text.markdown(f"**{status_message}**")
        
        # Update ETA
        if self.show_eta:
            elapsed = time.time() - self.start_time
            if progress > 0:
                eta = elapsed * (1 - progress) / progress
                self.eta_text.caption(f"Elapsed: {self._format_time(elapsed)} | ETA: {self._format_time(eta)}")
            else:
                self.eta_text.caption(f"Elapsed: {self._format_time(elapsed)}")
    
    def next_stage(self, status_message: Optional[str] = None):
        """Advance to the next stage.
        
        Args:
            status_message: Optional status message to display
        """
        self.current_stage += 1
        progress = self.current_stage / len(self.stages)
        self.update_progress(progress, status_message)
        
        # Re-render stage indicators
        self._render_stage_indicators()
    
    def complete(self, success_message: str = "Complete!"):
        """Mark the operation as complete.
        
        Args:
            success_message: Message to display on completion
        """
        self.update_progress(1.0, success_message)
        total_time = time.time() - self.start_time
        
        st.success(f"✓ {success_message} (Total time: {self._format_time(total_time)})")
    
    def _format_time(self, seconds: float) -> str:
        """Format time in seconds to human-readable string."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"


class FileUploadProgress:
    """Progress tracking for file upload operations."""
    
    def __init__(self, file_name: str, file_size: int):
        """Initialize upload progress tracker.
        
        Args:
            file_name: Name of the file being uploaded
            file_size: Size of the file in bytes
        """
        self.file_name = file_name
        self.file_size = file_size
        self.uploaded = 0
        
        # Create progress display
        st.subheader(f"📤 Uploading: {file_name}")
        self.progress_bar = st.progress(0)
        self.status = st.empty()
        
        # Show file size
        self.status.info(f"Size: {self._format_size(file_size)}")
    
    def update(self, bytes_uploaded: int):
        """Update upload progress.
        
        Args:
            bytes_uploaded: Total bytes uploaded so far
        """
        self.uploaded = bytes_uploaded
        progress = self.uploaded / self.file_size if self.file_size > 0 else 0
        
        self.progress_bar.progress(min(progress, 1.0))
        
        status_text = f"Uploaded: {self._format_size(self.uploaded)} / {self._format_size(self.file_size)}"
        if progress >= 1.0:
            self.status.success(f"✓ {status_text}")
        else:
            self.status.info(status_text)
    
    def complete(self, message: str = "Upload complete!"):
        """Mark upload as complete."""
        self.progress_bar.progress(1.0)
        self.status.success(f"✓ {message}")
    
    def error(self, error_message: str):
        """Mark upload as failed."""
        self.status.error(f"❌ Upload failed: {error_message}")
        self.progress_bar.empty()
    
    def _format_size(self, size_bytes: int) -> str:
        """Format byte size to human-readable string."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


# Convenience function for quick progress tracking
def with_progress(
    operation: Callable,
    stages: list[str],
    title: str = "Processing",
) -> any:
    """Execute an operation with progress tracking.
    
    Args:
        operation: Function that takes a ProgressTracker and returns result
        stages: List of stage names
        title: Title for progress display
        
    Returns:
        Result from the operation
        
    Example:
        def do_work(tracker):
            tracker.next_stage("Uploading")
            upload_file()
            tracker.next_stage("Processing")
            process_data()
            tracker.complete()
            return result
            
        result = with_progress(do_work, ["Upload", "Process", "Analyze"])
    """
    tracker = ProgressTracker(stages=stages, title=title)
    try:
        result = operation(tracker)
        return result
    except Exception as e:
        tracker.status_text.error(f"❌ Error: {str(e)}")
        raise
