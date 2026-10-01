# PHASE 3 — CONTEXT ENGINE IMPLEMENTATION

## Architecture
The new `ContextEngine` acts as the single logical authority for gathering, deduplicating, budgeting, and rendering context.

### Scopes
Context is isolated into boundaries defined in `src/context_engine/scopes.py`.
- **UserScope**: Global user memory and preferences.
- **ProjectScope**: Workspace paths and RAG knowledge.
- **TaskScope**: The active document and current turn history.

### Gatherers
Gatherers asynchronously fetch context.
- **MemoryGatherer**: Fetches pinned and recalled memories.
- **RAGGatherer**: Fetches relevant chunks from VectorRAG.
- **WebGatherer**: Generates search queries and fetches results.

### Deduplication
`Deduplicator` ensures overlapping context (e.g., RAG vs Active Document) doesn't bloat the prompt, prioritizing the most definitive source (Active Document > RAG).

### Budgeting
`ContextBudgeter` evaluates `token_estimate` against the dynamic model limit, dropping items by priority queue when budgets are exceeded.

### Rendering
Provider-specific rendering handles the exact `messages` payload shape (e.g., Anthropic's empty-content rules, Gemini's `extra_content` echoes).

## Migration Status
- [x] Singleton mutable state bug in `ChatProcessor` fixed.
- [x] Core `ContextEngine`, `ContextRequest`, `ContextItem` models created.
- [x] Scopes defined for Student Intelligence readiness.
- [x] Base gatherers, deduplicator, budgeter, and renderer structures established.
- [x] Complete replacement of raw context assembly via `ContextEngine` intercepting `_trim_route_request_messages`.
- [x] Provider-specific renderers (Anthropic, DeepSeek, Gemini, Default) implemented.
- [x] ContextEngine Deduplicator and Budgeter wired to production path.

## Known Limitations
- The current implementation maintains a compatibility layer through `ChatProcessor` to ensure zero disruption to `stream_agent_loop` during the migration.
- `MemoryManager.load()` still performs full file parses until the persistence layer is upgraded in a later phase.
