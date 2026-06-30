"""Candidate and ParsedResume models."""

from sqlalchemy import Column, String, Integer, Text, DateTime
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel
from backend.models.base import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String)
    resume_url = Column(String)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "resume_url": self.resume_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ParsedResume(Base):
    __tablename__ = "parsed_resumes"

    candidate_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String)
    skills_json = Column("skills", Text, default="[]")
    experiences_json = Column("experiences", Text, default="[]")
    education_json = Column("education", Text, default="[]")
    years_experience = Column(Integer, default=0)
    raw_response = Column(Text)
    parsed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def skills(self) -> List[dict]:
        import json
        return json.loads(self.skills_json)

    @skills.setter
    def skills(self, value: List[dict]):
        import json
        self.skills_json = json.dumps(value)

    @property
    def experiences(self) -> List[dict]:
        import json
        return json.loads(self.experiences_json)

    @experiences.setter
    def experiences(self, value: List[dict]):
        import json
        self.experiences_json = json.dumps(value)

    @property
    def education(self) -> List[dict]:
        import json
        return json.loads(self.education_json)

    @education.setter
    def education(self, value: List[dict]):
        import json
        self.education_json = json.dumps(value)

    def to_dict(self):
        return {
            "candidate_id": self.candidate_id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "skills": self.skills,
            "experiences": self.experiences,
            "education": self.education,
            "years_experience": self.years_experience,
            "parsed_at": self.parsed_at.isoformat() if self.parsed_at else None,
        }


# Pydantic models for validation
class SkillModel(BaseModel):
    name: str
    years: int = 0
    category: str = "skill"


class ExperienceModel(BaseModel):
    company: str
    role: str
    start: str
    end: Optional[str] = None
    summary: str = ""


class EducationModel(BaseModel):
    institution: str
    degree: str
    year: Optional[int] = None


class ParsedResumeModel(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    skills: List[SkillModel] = []
    experiences: List[ExperienceModel] = []
    education: List[EducationModel] = []
    years_experience: int = 0
