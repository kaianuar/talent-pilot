"""Job model."""

from sqlalchemy import Column, String, Integer, Text, DateTime
from datetime import datetime, timezone
from backend.models.base import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    required_skills_json = Column("required_skills", Text, nullable=False)
    preferred_skills_json = Column("preferred_skills", Text, default="[]")
    min_years = Column(Integer, nullable=False, default=0)
    description = Column(Text, default="")
    recruiter_email = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def required_skills(self):
        import json
        return json.loads(self.required_skills_json)

    @required_skills.setter
    def required_skills(self, value):
        import json
        self.required_skills_json = json.dumps(value)

    @property
    def preferred_skills(self):
        import json
        return json.loads(self.preferred_skills_json)

    @preferred_skills.setter
    def preferred_skills(self, value):
        import json
        self.preferred_skills_json = json.dumps(value)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "company": self.company,
            "required_skills": self.required_skills,
            "preferred_skills": self.preferred_skills,
            "min_years": self.min_years,
            "description": self.description,
            "recruiter_email": self.recruiter_email,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
