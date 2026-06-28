# TalentPilot Screening Architecture

## Overview

This document describes the hybrid architecture combining **Hexagonal Architecture** (Ports & Adapters) with **LangGraph** for workflow orchestration.

## Architecture Philosophy

We combine two architectural patterns to get the best of both worlds:

1. **Hexagonal Architecture** for domain logic
   - Pure, testable business rules
   - Clear boundaries via ports (interfaces)
   - Dependency inversion principle

2. **LangGraph** for workflow orchestration
   - Explicit state machine visualization
   - Built-in checkpointing and persistence
   - Easy human-in-the-loop integration

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  PRESENTATION LAYER (Streamlit / FastAPI)                        │
│  - Handles HTTP/WebSocket requests                                │
│  - Renders UI components                                          │
│  - Delegates to Application Services                              │
└──────────────────────┬───────────────────────────────────────────┘
                       │ Uses
┌──────────────────────▼───────────────────────────────────────────┐
│  APPLICATION LAYER (Hexagonal)                                    │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  USE CASES                                                  │ │
│  │  - ConductScreeningUseCase                                   │ │
│  │  - GenerateQuestionsUseCase                                  │ │
│  │  - AssessAnswerUseCase                                       │ │
│  └────────────────────┬─────────────────────────────────────────┘ │
│                       │ Injects                                  │
│  ┌────────────────────▼─────────────────────────────────────────┐ │
│  │  PORTS (Interfaces)                                          │ │
│  │  - QuestionGenerator (driven)                                │ │
│  │  - AnswerAssessor (driven)                                   │ │
│  │  - ScreeningRepository (driven)                              │ │
│  │  - EventPublisher (driving)                                    │ │
│  └───────────────────────────────────────────────────────────────┘ │
└──────────────────────┬───────────────────────────────────────────┘
                       │ Implements
┌──────────────────────▼───────────────────────────────────────────┐
│  INFRASTRUCTURE LAYER (Adapters)                                  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  LANGGRAPH ORCHESTRATION (Optional)                         │ │
│  │                                                              │ │
│  │  ┌──────────────────────────────────────────────────────┐   │ │
│  │  │  State Graph                                          │   │ │
│  │  │                                                      │   │ │
│  │  │  ┌─────────┐     ┌──────────────┐     ┌─────────┐  │   │ │
│  │  │  │ generate│────▶│  awaiting    │────▶│ assess  │  │   │ │
│  │  │  │question │     │   answer     │     │ answer  │  │   │ │
│  │  │  └─────────┘     └──────────────┘     └────┬────┘  │   │ │
│  │  │                                              │      │   │ │
│  │  │                     ┌──────────────────────────┘      │   │ │
│  │  │                     │                               │   │ │
│  │  │                     ▼                               │   │ │
│  │  │              ┌─────────────┐     ┌─────────┐        │   │ │
│  │  │              │  route      │────▶│ generate│        │   │ │
│  │  │              │  after        │     │ probe   │        │   │ │
│  │  │              │  assessment   │────▶│ draft   │        │   │ │
│  │  │              │               │     │ email   │        │   │ │
│  │  │              └─────────────┘     └─────────┘        │   │ │
│  │  │                                                      │   │ │
│  │  └──────────────────────────────────────────────────────┘   │ │
│  │                                                              │ │
│  │  Key Features:                                               │ │
│  │  - Nodes call domain services (hexagonal)                     │ │
│  │  - Conditional edges route flow                              │ │
│  │  - State checkpoints at each node                              │ │
│  │  - Human-in-loop at awaiting_answer                            │ │
│  │                                                              │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  EXTERNAL ADAPTERS                                           │ │
│  │  - LLMQuestionGenerator (Qwen/OpenAI)                        │ │
│  │  - SQLiteScreeningRepository                                 │ │
│  │  - StreamlitEventPublisher                                   │ │
│  │  - LangGraphCheckpointAdapter                                │ │
│  └───────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. Why Hybrid Architecture?

**Hexagonal Alone:**
- ✅ Pure, testable business logic
- ✅ Clear boundaries
- ❌ Manual workflow orchestration
- ❌ Complex state management

**LangGraph Alone:**
- ✅ Easy workflow definition
- ✅ Built-in persistence
- ❌ Business logic mixed with orchestration
- ❌ Harder to unit test

**Hybrid:**
- ✅ Hexagonal: Pure domain logic
- ✅ LangGraph: Clean orchestration
- ✅ Both layers independently testable
- ✅ Easy to swap implementations

### 2. State Management Strategy

```python
# LangGraph State (Orchestration Layer)
class ScreeningGraphState(TypedDict):
    screening_session: ScreeningSession  # Domain aggregate
    current_node: str
    user_input: Optional[str]
    # ... orchestration state only

# Domain State (Business Logic Layer)
class ScreeningSession:
    status: ScreeningStatus  # Pure domain state
    question_nodes: List[QuestionNode]  # Business invariants
    # ... no orchestration concerns
```

**Rule:** Domain entities never know about LangGraph. They expose methods that LangGraph nodes call.

### 3. Testing Strategy

**Domain Layer (No LangGraph):**
```python
def test_screening_session_invariants():
    session = ScreeningSession(...)
    questions = [Question(...), Question(...)]
    
    session.start_screening(questions)
    
    assert session.status == ScreeningStatus.IN_PROGRESS
    assert len(session.question_nodes) == 2
```

**Orchestration Layer (LangGraph):**
```python
def test_graph_flow():
    graph = create_screening_graph(...)
    
    initial_state = create_initial_state(...)
    
    # Run one node
    result = graph.invoke(initial_state, {"configurable": {"run_id": "test"}})
    
    assert result["current_node"] == "awaiting_answer"
```

## Getting Started

### Running the Application

```bash
# Install dependencies
pip install -r backend/requirements.txt

# Run with LangGraph visualization
python -m backend.main --with-langgraph

# Run without LangGraph (pure hexagonal)
python -m backend.main --no-langgraph
```

### Running Tests

```bash
# Unit tests (domain only, no LangGraph)
pytest tests/unit/domain/ -v

# Integration tests (with LangGraph)
pytest tests/integration/langgraph/ -v

# All tests
pytest tests/ -v
```

## Future Enhancements

1. **LangGraph Studio Integration**
   - Visual workflow editing
   - Real-time debugging
   - State inspection

2. **Multi-Agent Screening**
   - Technical interviewer agent
   - Culture fit agent
   - Consensus assessment

3. **Adaptive Question Generation**
   - RAG for job-specific questions
   - Candidate history awareness
   - Difficulty adjustment

## Questions?

See the following files for detailed implementation:
- `backend/domain/` — Hexagonal domain layer
- `backend/infrastructure/orchestration/` — LangGraph integration
- `backend/application/` — Application services and ports
