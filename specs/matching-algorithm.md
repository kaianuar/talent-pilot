# Matching Algorithm Spec

## Overview
The matching engine computes a composite fit score between a candidate (parsed resume) and a job listing. It combines four independent signals with fixed weights.

## Formula

```
Score = 0.35 × required_coverage
      + 0.20 × adjacent_bonus
      + 0.20 × experience_score
      + 0.25 × reasoning_score
```

## Signal 1: Required Coverage (weight: 0.35)

**What**: Fraction of the job's required skills that the candidate possesses.

**Algorithm**:
1. Normalize both skill names (lowercase + alias resolution)
2. For each required skill in the job:
   - If candidate has the canonical skill → count as matched
   - Else → count as missing
3. `required_coverage = matched_count / total_required`

**Alias resolution** (`backend/agent/aliases.py`):
- 150+ aliases mapping variations to canonical forms
- Examples: `React.js` → `react`, `K8s` → `kubernetes`, `Golang` → `go`, `Node.js` → `node`
- Case-insensitive: `Python` == `python` == `PYTHON`

**Edge cases**:
- No required skills → coverage = 1.0 (vacuous truth)
- All skills matched → coverage = 1.0
- No skills matched → coverage = 0.0

## Signal 2: Adjacent Bonus (weight: 0.20)

**What**: Credit for transferable skills the candidate has that are similar to missing required skills.

**Algorithm**:
1. For each required skill the candidate does NOT have:
   - Look up the skill in `ADJACENT_SKILLS` dict
   - If the candidate has ANY adjacent skill → count as adjacent hit
2. `adjacent_bonus = (adjacent_hits / total_required) × 0.5`

**Adjacent skills graph** (`backend/agent/aliases.py`):
- 100+ entries mapping skills to their transferable neighbors
- Domain-specific: backend skills map to backend, frontend to frontend
- Examples:
  - `python` ↔ `ruby`, `go`, `typescript`
  - `react` ↔ `vue`, `angular`, `svelte`
  - `postgresql` ↔ `mysql`, `sql server`, `sqlite`
  - `aws` ↔ `azure`, `google cloud`
  - `pytorch` ↔ `tensorflow`
  - `kubernetes` ↔ `docker`, `nomad`

**Max bonus**: 0.5 (when ALL required skills have adjacent matches)

## Signal 3: Experience Score (weight: 0.20)

**What**: How well the candidate's years of experience match the job's minimum.

**Formula**:
```
experience_score = min(1.0, candidate.years_experience / job.min_years)
```

**Examples**:
- Job requires 5 years, candidate has 6 → score = 1.0 (capped)
- Job requires 5 years, candidate has 3 → score = 0.6
- Job requires 0 years → score = 1.0 (no minimum)

## Signal 4: Reasoning Score (weight: 0.25)

**What**: LLM-based holistic assessment of fit.

**Model**: qwen3-max (DashScope International)

**Prompt**:
```
Given this candidate JSON and this job JSON, rate the fit 0.0-1.0
considering depth of experience, project relevance, and trajectory.
Reply with a single decimal number, nothing else.
```

**Input**: Serialized candidate and job JSON objects.

**Output parsing**: Extract float from response, clamp to [0.0, 1.0].

**Fallback**: If LLM call fails, score defaults to 0.5 (neutral).

**Caching**: Results are cached in the database keyed by `(candidate_id, job_id)` to avoid redundant LLM calls.

## Tier Classification

| Tier | Score Range | Behavior |
|------|-------------|----------|
| `STRONG_MATCH` | ≥ 0.75 | Proceed directly to screening questions |
| `PARTIAL_MATCH` | ≥ 0.55 | Ask clarifying questions about gaps |
| `WEAK_MATCH` | ≥ 0.40 | Ask but warn candidate about significant gaps |
| `NO_MATCH` | < 0.40 | Reject with reasoning and improvement suggestions |

## Ranking

`rank_matches(candidate, jobs, top_n=5)`:
1. Compute `match_score` for each job
2. Sort by composite score descending
3. Return top N results

## Testing

14 tests covering:
- Skill normalization (exact, alias, unknown)
- Full match → STRONG_MATCH
- Partial match → WEAK_MATCH
- Adjacent skill bonus
- Irrelevant skills → NO_MATCH
- Experience capping at 1.0
- Underqualified experience scaling
- Score boundary at 0.75
- Top-N ranking
- All MatchResult fields present
- No required skills edge case
- Alias normalization in matching

## Tuning Guide

To adjust matching behavior, modify these in `backend/config.py`:
- `W_REQUIRED`, `W_ADJACENT`, `W_EXPERIENCE`, `W_REASONING` — signal weights
- `SCORE_STRONG`, `SCORE_PARTIAL`, `SCORE_WEAK` — tier thresholds

To add new skill aliases or adjacent mappings, edit `backend/agent/aliases.py`.
