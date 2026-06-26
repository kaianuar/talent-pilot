"""Application model."""

from sqlalchemy import Column, String, Float, Text, DateTime
from datetime import datetime
from backend.models.base import Base


class Application(Base):
    __tablename__ = "applications"

    id = Column(String, primary_key=True)
    candidate_id = Column(String, nullable=False)
    job_id = Column(String, nullable=False)
    match_score = Column(Float, nullable=False)
    match_tier = Column(String, nullable=False)
    screening_answers_json = Column("screening_answers", Text, default="{}")
    status = Column(String, nullable=False, default="pending")
    email_message_id = Column(String)
    email_error = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    @property
    def screening_answers(self):
        import json
        return json.loads(self.screening_answers_json)

    @screening_answers.setter
    def screening_answers(self, value):
        import json
        self.screening_answers_json = json.dumps(value)

    def to_dict(self):
        return {
            "id": self.id,
            "candidate_id": self.candidate_id,
            "job_id": self.job_id,
            "match_score": self.match_score,
            "match_tier": self.match_tier,
            "screening_answers": self.screening_answers,
            "status": self.status,
            "email_message_id": self.email_message_id,
            "email_error": self.email_error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
