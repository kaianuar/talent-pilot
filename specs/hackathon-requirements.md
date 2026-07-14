# Hackathon Requirements Spec

## Event
**1st Qwen Cloud Global AI Hackathon**

## Track
**Track 4: Autopilot Agent**
- End-to-end business workflow automation
- Ambiguous input handling
- Human-in-the-loop at critical points
- Production-readiness over toy demos

## Deadline
**EXTENDED: July 20, 2026, 2:00 PM PDT** (originally July 9; see [Devpost Updates](https://qwencloud-hackathon.devpost.com/updates) and the official [Qwen Cloud announcement](https://www.qwencloud.com/challenge/hackathon))

## Judging Period
**July 28 – August 11, 2026** (per Devpost Rules page)

## Prize Structure

| Place | Cash | Cloud Credits |
|-------|------|---------------|
| Grand Prize (per winner) | $7,000 | $3,000 |
| Honorable Mention | $500 | $500 |
| Blog Post Prize | $1,000 | — |

## Judging Criteria

| Criterion | Weight | How We Address It |
|-----------|--------|-------------------|
| Innovation & AI Creativity | 30% | 6 MCP tools, adjacent-skill graph, composite scoring, Qwen3-VL-Plus for CV parsing |
| Technical Depth | 30% | Modular architecture, retry logic, audit logging, Pydantic validation, SQLAlchemy ORM |
| Problem Value | 25% | Real recruiting pain point, end-to-end automation, rejection with reasoning |
| Presentation | 15% | Architecture diagram, demo video, clear README, screenshots |

## Submission Requirements

### Required
- [x] Public GitHub repository with open-source license (MIT)
- [ ] ~3-minute demo video (YouTube/Vimeo, public)
- [ ] Proof of Alibaba Cloud deployment (separate recording + code link)
- [ ] Architecture diagram
- [ ] Text description identifying Track 4
- [ ] Devpost submission form

### Optional
- [ ] Blog post for Blog Post Prize ($1,000)

## Alibaba Cloud Deployment Proof

The rules require: "a link to a code file in their code repo that demonstrates use of Alibaba Cloud services and APIs."

**Primary evidence**: `backend/services/email.py`
- `import smtplib` + `smtpdm.aliyun.com` host string
- DirectMail SMTP integration

**Secondary evidence**:
- `deploy/Dockerfile` — container for Function Compute
- `deploy/nginx.conf` — reverse proxy configuration
- `deploy/deploy.sh` — ACR push script

## Qwen Cloud API Usage

Must use at least one Qwen Cloud model. We use three:

| Model | Usage | File |
|-------|-------|------|
| Qwen3-VL-Plus | CV PDF parsing (vision) | `backend/services/resume_parser.py` |
| qwen3-max | Match reasoning, screening questions, email drafting | `backend/agent/matching.py`, `backend/agent/tools.py` |
| qwen-turbo | Chat fallback (optional) | `backend/config.py` |

## Key URLs

| Resource | URL |
|----------|-----|
| Main page | https://www.qwencloud.com/challenge/hackathon |
| Devpost | https://qwencloud-hackathon.devpost.com/ |
| Voucher application | https://www.qwencloud.com/challenge/hackathon/voucher-application |
| API keys | https://home.qwencloud.com/api-keys |
| Discord | https://discord.gg/cDEHSV4Qqj |
| Resources | https://qwencloud-hackathon.devpost.com/resources |

## Timeline

| Date | Event |
|------|-------|
| May 26, 2026 | Hackathon launch |
| Jul 8, 2026 | Build period ends |
| Jul 9, 2026 2:00 PM PDT | Submission deadline |
| Jul 10-30, 2026 | Judging |
| Aug 7, 2026 | Winners announced |

## Our Differentiators

1. **Adjacent-skill modeling**: 150+ skill mappings — not just keyword matching
2. **Composite scoring**: 4 weighted signals, not a single LLM call
3. **Defense-in-depth HITL**: prompt + code + API + frontend quadruple guard
4. **Rejection with reasoning**: agent tells candidates WHY and suggests improvements
5. **Full audit trail**: every action logged for transparency
6. **Real email delivery**: Alibaba DirectMail, not mock

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Qwen Cloud rate limits | Exponential backoff, caching |
| CV parsing errors | Retry with stricter prompt, graceful degradation |
| Email delivery failure | 3 retries with backoff, audit logging |
| Container cold start | Acceptable for demo, min instances for production |
| SQLite persistence | Acceptable for demo, swap to RDS for production |
