# Phase 0: Aurex Student Intelligence Audit

## Overview
This document summarizes the audit of the existing Aurex codebase to prepare for the implementation of the Aurex Student Intelligence feature. The primary goal is to identify existing infrastructure that can be reused and avoid duplicating functionality.

## Core Directories Audited

### 1. `src/context_engine/`
- **Purpose**: Manages the assembly and prioritization of context to be sent to the LLM.
- **Key Files**: 
  - `engine.py`, `context_waterfall.py`, `budgeter.py`
  - `gatherers/` (`rag.py`, `web.py`, `memory.py`, `runtime.py`)
  - `renderer/` (provider specific renderers like `anthropic.py`, `gemini.py`)
- **Reuse Potential**: Can be extended with a new gatherer specifically for student context (e.g., current syllabus, flashcard review states, learning goals) without rebuilding the core context waterfall and deduplication logic.

### 2. `src/provider_intelligence/`
- **Purpose**: Handles routing and model capabilities management.
- **Key Files**: `routing_engine.py`, `candidate_selector.py`, `health_manager.py`, `model_registry.py`.
- **Reuse Potential**: The student intelligence feature can register specialized "student" or "teacher" models/capabilities here, leveraging the existing fallback and health management infrastructure.

### 3. `src/executor/`
- **Purpose**: Manages execution and safety boundaries.
- **Key Files**: `executor.py`, `docker_manager.py`, `policy.py`, `audit.py`.
- **Reuse Potential**: Use the existing Docker sandbox for executing student code or sandboxed tools, adhering to existing policies.

## Component Audits

### ToolRegistry & PolicyEngine
- Implemented across `src/tool_index.py`, `src/tool_policy.py`, `src/tool_capabilities.py`.
- Allows fine-grained access control (disabling/enabling tools). 

### SecureExecutor & Agent Runtime
- The core loop (`agent_loop.py`) already contains conceptual frameworks for "student" vs "teacher" (Tier 1 vs Tier 2) execution and escalation (`ask_teacher`).

### RAG & Memory
- **RAG**: Handled by `rag_manager.py`, `rag_vector.py`, and `rag_singleton.py`.
- **Memory**: Persistent facts are stored via memory components (e.g., `manage_memory`). Note that `agent_loop.py` explicitly states *not* to use memory for notes or tasks, reserving it for persistent user preferences and facts.

### Document Ingestion & PDF Processing
- Supported natively via `pdf_runtime.py`, `pdf_forms.py`, `upload_handler.py`. These can be used directly for importing syllabi, textbook chapters, and past exams.

### Reminders, Scheduling, and Existing Task Systems
- **Notes/Todos/Reminders**: Consolidated under `manage_notes` (in `src/tools/notes.py` and references). Supports checklists, types, and `due_date`.
- **Calendar**: Handled by `manage_calendar` (in `src/tools/calendar.py`).
- **Recurring/Background Tasks**: Handled by `manage_tasks` (in `task_scheduler.py`, `task_endpoint.py`).

## Findings on Existing Student/Educational Features
- **Student/Teacher Paradigm**: Already exists natively in the agent architecture (`agent_loop.py` uses "student" for standard execution and escalates to "teacher").
- **Flashcards/Quizzes**: No explicit `flashcard_manager` or `quiz_system` found in the tool registry. These will need to be developed, but should integrate with the existing `manage_notes` or a new database schema rather than duplicating the underlying storage model.
- **Knowledge Systems**: Existing RAG, document, and memory systems are robust enough to store knowledge, but a specialized ontology for educational tracking (e.g., Spaced Repetition states) will need to be added.
- **Project Systems**: Basic tools exist for browsing the workspace and codebase (`tools/research.py`, `agent_loop.py` path resolution).

## Recommendations for Phase 1
1. **Extend Notes/Tasks**: Rather than building a separate reminder system for students, inject student intelligence triggers into the existing `manage_tasks` and `manage_notes` (with `due_date`).
2. **Flashcards/Quizzes**: Implement as new specialized tools (`manage_flashcards`, `take_quiz`), backed by the existing RAG storage for content, but with bespoke tracking for spaced repetition.
3. **Context Gatherer**: Add a `student_state` gatherer to `context_engine` to pre-load relevant study materials based on the upcoming schedule and past performance.
