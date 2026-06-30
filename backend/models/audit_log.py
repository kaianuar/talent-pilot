"""Audit log model."""

from sqlalchemy import Column, String, Text, DateTime
from datetime import datetime, timezone
from backend.models.base import Base


class AuditLogEntry(Base):
    __tablename__ = "audit_log"

    id = Column(String, primary_key=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    action = Column(String, nullable=False)
    candidate_id = Column(String)
    details_json = Column("details", Text, default="{}")
    status = Column(String, default="ok")

    @property
    def details(self):
        import json
        return json.loads(self.details_json)

    @details.setter
    def details(self, value):
        import json
        self.details_json = json.dumps(value)

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "action": self.action,
            "candidate_id": self.candidate_id,
            "details": self.details,
            "status": self.status,
        }
