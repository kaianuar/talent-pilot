# Backend Review Brief: Hexagonal + LangGraph Hybrid Architecture

## Overview

This review covers the implementation of a **hybrid architecture** combining:
1. **Hexagonal Architecture** (Ports & Adapters) for domain logic
2. **LangGraph** for workflow orchestration

## Architecture Goals

- ✅ **Clean Domain Layer**: Pure business logic, no infrastructure dependencies
- ✅ **Explicit Workflow**: State machine with LangGraph nodes and edges
- ✅ **Testability**: Domain layer fully unit testable without LangGraph
- ✅ **Flexibility**: Easy to swap LLM providers, persistence, or orchestration

## Files to Review

### Domain Layer (Hexagonal - Core)
| File | Purpose | Lines |
|------|---------|-------|
| `backend/domain/entities/screening_session.py` | Aggregate root with business invariants | ~250 |
| `backend/domain/value_objects/question.py` | Immutable Question and Answer types | ~120 |
| `backend/domain/value_objects/assessment.py` | AnswerAssessment with quality logic | ~100 |
| `backend/domain/services/answer_assessor.py` | Domain service for answer assessment | ~200 |

### Application Layer (Hexagonal - Ports & Use Cases)
| File | Purpose | Lines |
|------|---------|-------|
| `backend/application/ports/question_generator.py` | Interface port for question generation | ~100 |
| `backend/application/use_cases/conduct_screening.py` | Main use case orchestrator | ~150 |
| `backend/application/services/screening_orchestrator.py` | Application service for screening | ~400 |

### Infrastructure Layer (Adapters)
| File | Purpose | Lines |
|------|---------|-------|
| `backend/infrastructure/adapters/llm_question_generator.py` | LLM implementation of QuestionGenerator | ~200 |
| `backend/infrastructure/adapters/sqlite_repository.py` | SQLite persistence for ScreeningSession | ~250 |
| `backend/infrastructure/orchestration/graph_builder.py` | LangGraph graph construction | ~500 |
| `backend/infrastructure/orchestration/langgraph_schema.py` | LangGraph state schema | ~150 |

### Documentation
| File | Purpose |
|------|---------|
| `backend/ARCHITECTURE.md` | Full architecture design document |
| `backend/REVIEW_BRIEF.md` | This file |

## Review Checklist

### 1. Hexagonal Structure Implementation

- [ ] **Domain Layer Isolation**: Domain entities have NO dependencies on infrastructure (LangGraph, SQLite, LLM clients)
- [ ] **Ports are Interfaces**: All ports (`QuestionGenerator`, etc.) are proper Python `Protocol` or `ABC` classes
- [ ] **Dependency Direction**: Dependencies point inward (Infrastructure → Application → Domain)
- [ ] **No Leaky Abstractions**: Domain entities don't expose infrastructure concerns (no `to_dict_for_json()` methods)

**Specific Checks:**
- [ ] `ScreeningSession` has no imports from `langgraph`, `sqlite3`, `openai`
- [ ] `QuestionGenerator` is a Protocol, not a concrete class
- [ ] `AnswerAssessor` accepts LLM client via injection, not global import

### 2. LangGraph Implementation Accuracy

- [ ] **State Schema Correctness**: `ScreeningGraphState` is a proper `TypedDict` with correct annotations
- [ ] **Node Functions**: All node functions have correct signature `(state: State) -> State`
- [ ] **Edge Routing**: Conditional edges return valid node names or `END`
- [ ] **Graph Compilation**: Graph compiles without errors
- [ ] **State Immutability**: Nodes return new state, don't mutate in place

**Specific Checks:**
- [ ] `generate_question_node` returns state with `generated_question_text` set
- [ ] `assess_answer_node` calls domain service, not inline logic
- [ ] `route_after_assessment` returns one of: `"ask_question"`, `"draft_email"`, `"end"`, `"error"`

### 3. No Leftover Code Breaking Structure

- [ ] **No Old Code in Domain**: Old prompt-based logic removed from domain entities
- [ ] **No Direct LLM Calls in Domain**: All LLM calls go through ports/adapters
- [ ] **No Global State**: No module-level variables holding state
- [ ] **No Circular Imports**: Verify with `python -c "import backend"`

**Specific Checks:**
- [ ] `backend/domain/` has no `openai` imports
- [ ] `backend/agent/` old code is deleted or deprecated
- [ ] `backend/models/` (SQLAlchemy) not mixed with domain entities
- [ ] No `from backend.app import app` in domain layer

### 4. Pythonic & SOLID Principles

#### S - Single Responsibility Principle
- [ ] Each class has one reason to change
- [ ] `ScreeningSession` manages session lifecycle
- [ ] `AnswerAssessor` assesses answers only
- [ ] `QuestionGenerator` generates questions only

#### O - Open/Closed Principle
- [ ] New question types without modifying `Question`
- [ ] New assessment strategies without modifying `AnswerAssessor`
- [ ] New LLM providers without modifying domain

#### L - Liskov Substitution Principle
- [ ] `LLMQuestionGenerator` can substitute any `QuestionGenerator`
- [ ] Mock adapters can substitute real adapters in tests

#### I - Interface Segregation Principle
- [ ] `QuestionGenerator` doesn't force implementation of unused methods
- [ ] Separate ports for different concerns (generation vs assessment)

#### D - Dependency Inversion Principle
- [ ] Domain depends on abstractions (ports), not concrete implementations
- [ ] `ScreeningOrchestrator` receives `QuestionGenerator` via constructor
- [ ] `AnswerAssessor` receives LLM client via injection, not global import

#### Pythonic Practices
- [ ] Type hints throughout (`typing`, `TypedDict`, `Protocol`)
- [ ] Dataclasses for value objects
- [ ] `Optional[]` instead of `| None` (Python 3.9+)
- [ ] Docstrings with Args/Returns
- [ ] Context managers (`with` statements) for resources
- [ ] List/dict comprehensions where readable
- [ ] `isinstance()` not `type() == `
- [ ] No bare `except:` clauses

## Running the Review

### Automated Checks

```bash
# 1. Check for circular imports
python -c "import backend"

# 2. Run type checker
mypy backend/ --ignore-missing-imports

# 3. Run linter
ruff check backend/

# 4. Run tests
pytest tests/unit/domain/ -v
pytest tests/integration/langgraph/ -v

# 5. Check for forbidden imports in domain
./scripts/check_domain_isolation.sh
```

### Manual Review

1. **Read `ARCHITECTURE.md`** — Understand the design intent
2. **Review domain layer** — `backend/domain/` — Ensure no infrastructure leaks
3. **Review application ports** — `backend/application/ports/` — Check interfaces are clean
4. **Review LangGraph integration** — `backend/infrastructure/orchestration/` — Verify graph structure
5. **Trace a full flow** — Follow a screening from start to finish through all layers
6. **Check tests** — Verify test coverage and independence from infrastructure

## Expected Outcomes

After the review, we should have:

1. ✅ **Clean hexagonal architecture** — Domain isolated from infrastructure
2. ✅ **Working LangGraph integration** — State machine orchestrates domain
3. ✅ **No code smells** — SOLID principles followed
4. ✅ **Comprehensive tests** — Unit and integration tests pass
5. ✅ **Documentation** — Architecture and code are well-documented
6. ✅ **Review report** — Detailed findings and recommendations

---

**Ready to begin the review!** 🚀
