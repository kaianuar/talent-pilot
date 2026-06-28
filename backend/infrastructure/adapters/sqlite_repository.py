"""SQLite repository adapter for screening session persistence.

This adapter implements the ScreeningRepository port (to be defined)
for persisting ScreeningSession aggregates to SQLite.
"""

import json
import sqlite3
from datetime import datetime
from typing import Optional
from pathlib import Path

from backend.domain.entities.screening_session import (
    ScreeningSession,
    ScreeningStatus,
    QuestionNode,
)
from backend.domain.value_objects.question import Question, QuestionType, QuestionPriority
from backend.domain.value_objects.assessment import AnswerAssessment, AnswerQuality, AssessmentDecision


class SQLiteScreeningRepository:
    """Repository adapter for persisting ScreeningSession to SQLite."""
    
    def __init__(self, db_path: str | Path):
        """Initialize repository with database path.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._ensure_schema()
    
    def _ensure_schema(self) -> None:
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS screening_sessions (
                    id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    match_tier TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    completed_at TEXT,
                    current_question_index INTEGER DEFAULT 0,
                    sufficient_evidence BOOLEAN DEFAULT 0,
                    termination_reason TEXT,
                    data_json TEXT NOT NULL
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_screening_candidate 
                ON screening_sessions(candidate_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_screening_job 
                ON screening_sessions(job_id)
            """)
            
            conn.commit()
    
    def save(self, session: ScreeningSession) -> None:
        """Save or update a screening session.
        
        Args:
            session: The ScreeningSession aggregate to persist
        """
        data = {
            "question_nodes": [
                {
                    "question": {
                        "id": node.question.id,
                        "text": node.question.text,
                        "type": node.question.type.value,
                        "priority": node.question.priority.value,
                        "focus_area": node.question.focus_area,
                        "expected_evidence": node.question.expected_evidence,
                        "follow_up_trigger": node.question.follow_up_trigger,
                    },
                    "answer": {
                        "question_id": node.answer.question_id,
                        "text": node.answer.text,
                        "timestamp": node.answer.timestamp,
                    } if node.answer else None,
                    "assessment": {
                        "quality": node.assessment.quality.value,
                        "confidence": node.assessment.confidence,
                        "key_points_identified": node.assessment.key_points_identified,
                        "gaps_identified": node.assessment.gaps_identified,
                        "decision": node.assessment.decision.value,
                        "reasoning": node.assessment.reasoning,
                    } if node.assessment else None,
                    "asked_at": node.asked_at.isoformat() if node.asked_at else None,
                    "answered_at": node.answered_at.isoformat() if node.answered_at else None,
                }
                for node in session.question_nodes
            ],
        }
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO screening_sessions (
                    id, candidate_id, job_id, status, match_tier,
                    created_at, updated_at, completed_at,
                    current_question_index, sufficient_evidence,
                    termination_reason, data_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.id,
                    session.candidate_id,
                    session.job_id,
                    session.status.value,
                    session.match_tier,
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                    session.completed_at.isoformat() if session.completed_at else None,
                    session.current_question_index,
                    1 if session.sufficient_evidence else 0,
                    session.termination_reason,
                    json.dumps(data),
                ),
            )
            conn.commit()
    
    def get_by_id(self, session_id: str) -> Optional[ScreeningSession]:
        """Retrieve a screening session by ID.
        
        Args:
            session_id: The session ID
            
        Returns:
            The ScreeningSession if found, None otherwise
        """
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT data_json FROM screening_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            
            if not row:
                return None
            
            # TODO: Deserialize from JSON
            # This requires implementing from_dict on domain entities
            # For now, return None
            return None
    
    def get_by_candidate_and_job(
        self,
        candidate_id: str,
        job_id: str,
    ) -> list[ScreeningSession]:
        """Get all screening sessions for a candidate-job pair.
        
        Args:
            candidate_id: The candidate ID
            job_id: The job ID
            
        Returns:
            List of ScreeningSession aggregates
        """
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id FROM screening_sessions WHERE candidate_id = ? AND job_id = ? ORDER BY created_at DESC",
                (candidate_id, job_id),
            ).fetchall()
            
            # TODO: Deserialize each row
            return []


__all__ = ["SQLiteScreeningRepository"]
