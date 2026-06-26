# Data Model Spec

## Database
- **Engine**: SQLite (file: `data/recruiter.db`)
- **ORM**: SQLAlchemy 2.0 with declarative base
- **Validation**: Pydantic models alongside ORM models

## Tables

### `jobs`
Seeded from `data/seed_jobs.json`. 32 realistic job listings across 8 categories.

| Column | Type | Description |
|--------|------|-------------|
| `id` | String (PK) | UUID, e.g. `job-001` |
| `title` | String | Job title |
| `company` | String | Company name |
| `required_skills` | Text (JSON) | Array of `{name, category, min_years, is_required}` |
| `preferred_skills` | Text (JSON) | Array of skill names |
| `min_years` | Integer | Minimum years of experience |
| `description` | Text | Job description |
| `recruiter_email` | String | Where applications are sent |
| `created_at` | DateTime | Creation timestamp |

**Required skills format**:
```json
{
  "name": "Python",
  "category": "language",
  "min_years": 4,
  "is_required": true
}
```

### `candidates`
Created when a CV is uploaded.

| Column | Type | Description |
|--------|------|-------------|
| `id` | String (PK) | UUID |
| `name` | String | Extracted from CV |
| `email` | String | Extracted from CV |
| `phone` | String | Extracted from CV |
| `resume_url` | String | Path to uploaded PDF |
| `created_at` | DateTime | Upload timestamp |

### `parsed_resumes`
1:1 with candidates. Stores the structured output from Qwen3-VL-Plus.

| Column | Type | Description |
|--------|------|-------------|
| `candidate_id` | String (PK) | FK to candidates |
| `name` | String | Extracted name |
| `email` | String | Extracted email |
| `phone` | String | Extracted phone |
| `skills` | Text (JSON) | Array of `{name, years, category}` |
| `experiences` | Text (JSON) | Array of `{company, role, start, end, summary}` |
| `education` | Text (JSON) | Array of `{institution, degree, year}` |
| `years_experience` | Integer | Total professional years |
| `raw_response` | Text | Raw LLM response |
| `parsed_at` | DateTime | Parse timestamp |

**Skills format**:
```json
{
  "name": "FastAPI",
  "years": 3,
  "category": "framework"
}
```

**Categories**: `language`, `framework`, `tool`, `database`, `cloud`, `platform`, `skill`

### `applications`
Created when a candidate applies to a job.

| Column | Type | Description |
|--------|------|-------------|
| `id` | String (PK) | UUID |
| `candidate_id` | String | FK to candidates |
| `job_id` | String | FK to jobs |
| `match_score` | Float | Composite match score (0.0–1.0) |
| `match_tier` | String | STRONG_MATCH / PARTIAL_MATCH / WEAK_MATCH / NO_MATCH |
| `screening_answers` | Text (JSON) | Dict of question → answer |
| `status` | String | pending → sending → sent / failed |
| `email_message_id` | String | DirectMail Message-ID |
| `email_error` | Text | Error message if failed |
| `created_at` | DateTime | Application timestamp |

### `audit_log`
Every action is logged for transparency.

| Column | Type | Description |
|--------|------|-------------|
| `id` | String (PK) | UUID |
| `timestamp` | DateTime | When the action occurred |
| `action` | String | e.g. `resume_uploaded`, `chat_turn`, `application_sent` |
| `candidate_id` | String | FK to candidates (nullable) |
| `details` | Text (JSON) | Action-specific metadata |
| `status` | String | ok / failed / rejected |

## Pydantic Validation Models

### `ParsedResumeModel`
Used to validate LLM output before storing.

```python
class ParsedResumeModel(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    skills: List[SkillModel] = []
    experiences: List[ExperienceModel] = []
    education: List[EducationModel] = []
    years_experience: int = 0
```

### `SkillModel`
```python
class SkillModel(BaseModel):
    name: str
    years: int = 0
    category: str = "skill"
```

## Seed Data

**32 jobs** across 8 categories:
- Backend (5): Senior Backend, Platform, Database, Infrastructure, Staff SWE
- Frontend (4): Lead Frontend, React Native, Frontend, Full Stack
- Data (4): Data Scientist, Senior Data Engineer, ML Researcher, Solutions Architect
- DevOps (4): Senior DevOps, SRE, Security, TPM
- Mobile (4): iOS, Android, React Native, Embedded
- ML/AI (4): ML Engineer, CV Engineer, ML Researcher, Data Scientist
- Design (3): Senior UX, Product Designer, Developer Advocate
- QA (3): QA Lead, Technical Writer, Game Dev

**10 test candidates** with realistic CVs in `data/test_resumes/`.
