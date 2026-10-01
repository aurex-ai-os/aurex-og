# AUREX — PHASE 3: CONTEXT ARCHITECTURE AUDIT

## 1. Executive Summary
Aurex currently assembles context per-request through a distributed set of functions primarily rooted in `routes/chat_helpers.py` (`build_chat_context`), `src/chat_processor.py` (`build_context_preface`), and `src/agent_loop.py` (`stream_agent_loop` / `_build_base_prompt`). It dynamically loads memory, retrieves RAG documents, and executes web searches, appending these as `untrusted_context_message` blocks. While highly capable, context assembly is decentralized, mutable across concurrent requests (due to a singleton `chat_processor`), and vulnerable to context duplication (e.g. active documents vs RAG vs tool results).

## 2. Current Context Architecture
The pipeline flow for a standard chat/agent request:
1. **USER INPUT**: Arrives at `routes/chat_routes.py` (`chat_stream` or `chat_endpoint`).
2. **SESSION**: Extracted parameters (session ID, workspace, active document, compare mode).
3. **CONTEXT BUILDER**: Calls `chat_helpers.build_chat_context()`.
4. **PREFACE**: Calls `chat_processor.build_context_preface()` which aggregates:
   - System prompts (presets)
   - Pinned and Extended Memory (`MemoryManager.load` / `_hybrid_retrieve`)
   - RAG chunks (`rag_manager.search`)
   - Web search results
5. **AGENT LOOP**: Passes context to `agent_loop.stream_agent_loop()`.
6. **PROMPT ASSEMBLY**: `_build_base_prompt()` injects Active Document, Workspace Rules, Uploaded Files, Local Computer Rules, and Email drafts.
7. **MODEL REQUEST**: Handled by `stream_llm_with_fallback`.
8. **TOOL CALLS**: LLM emits tool calls.
9. **TOOL RESULTS**: `_append_tool_results()` wraps outputs in `untrusted_context_message` blocks and appends to the `messages` array.
10. **NEXT ITERATION**: Loop repeats until completion.

## 3. Context Sources
Aurex draws context from the following systems:
- **Conversation History**: From `session.messages` / UI frontend.
- **Memory**: Pinned and recalled facts via `MemoryManager` (loaded from JSON).
- **RAG / Personal Docs**: ChromaDB-backed `VectorRAG` (`src/rag_vector.py`).
- **Web Search**: Dynamic query generation + search execution (injected in preface).
- **Active Document**: Fetched from DB via `active_doc_id` or session fallback, injected via `_minimal_aurex_doc_messages` or `_build_base_prompt`.
- **Email Drafts**: Fetched if `active_document.language == "email"`.
- **Uploaded Files**: Embedded via `build_uploaded_file_manifest`.
- **Tool Results**: Command output, file reads, web fetches.
- **Workspace Context**: Workspace paths and specific rules.
- **MCP Servers**: Dynamic external tools.
- **System Instructions**: Global instructions, tool schemas, and safety boundaries (`UNTRUSTED_CONTEXT_POLICY`).

## 4. Context Assembly Points
- `routes/chat_helpers.py:build_chat_context`: Main orchestration. Appends user messages, YouTube transcripts, pre-fetched search.
- `src/chat_processor.py:build_context_preface`: Injects Memory, RAG, Web Search.
- `src/agent_loop.py:_build_base_prompt`: Assembles the mega system prompt (Tools, Workspace, Active Doc).
- `src/agent_loop.py:_append_tool_results`: Appends tool executions.
- `src/agent_loop.py:_insert_before_latest_user`: Utilities for message re-ordering.

## 5. Token / Budget Systems
- `src/context_budget.py:compute_input_token_budget`: Sets the soft limit scaling off the model's context window (default 85% headroom, max 200k).
- `src/context_compactor.py:_truncate_text_to_token_budget`: Hard truncation.
- `src/context_compactor.py:trim_for_context`: Drops older messages to fit the budget.
- `src/context_compactor.py:_truncate_tool_call_args`: Prevents massive tool inputs.

## 6. Duplication Risks
- **Memory vs. Conversation**: An agent learns a fact -> stores in Memory. In the immediate next turns, the fact exists in the recent conversation history AND is injected again via the Memory `preface`.
- **Active Document vs. RAG vs. Tools**: The `active_document` is fully injected into the system prompt. If RAG indexes that document, it may retrieve the same text. If the agent calls `read_file` on it, the text is duplicated a third time in the tool output.
- **Reasoning Content Accumulation**: Documented in `_append_tool_results`, some providers (Nemotron) re-inject all prior `<think>` blocks if not pruned.

## 7. Leakage / Isolation Risks
- **Singleton Mutation (CRITICAL)**: `chat_processor` is passed as a shared singleton. In `build_context_preface` (line 311), it executes `self._last_used_memories = []` and mutates it. Concurrent requests across different users/sessions will overwrite this array, causing one user's request to log or utilize another user's memories.
- **Active Document ID Theft**: `chat_routes.py` (line 1399) correctly filters `_owner_session_filter(_doc_q, ctx.user)`, meaning strict ownership is applied. However, empty owner fields on legacy memory/docs could leak.

## 8. Mutable State Risks
- `self._last_used_memories` on `chat_processor` is mutated globally.
- `_research_flags = {"do": do_research}` is mutated locally.
- In `stream_agent_loop`, the `messages` list is appended to directly (`messages.append`), modifying the array passed in from the caller.

## 9. Agent Run Context
Multi-step runs are governed by `stream_agent_loop`.
- Initial context is passed via `messages`.
- After an LLM response containing tool calls, an `assistant` message (with `tool_calls`) is appended.
- Tools execute.
- A `tool` message (with `untrusted_context_message` formatting) is appended for each result.
- The loop continues. State is entirely contained within the growing `messages` array, not a specialized Planning State object.

## 10. RAG Integration
- Triggered automatically in `build_context_preface` if `use_rag=True`.
- Calls `rag_manager.search(message, k=5, owner=owner)`.
- Filters results by `RAG_SIMILARITY_THRESHOLD`.
- Formats chunks as `untrusted_context_message` and caps total RAG text at 10,000 chars.

## 11. Memory Integration
- Triggered in `build_context_preface`.
- Loads all memories via `memory_manager.load(owner=owner)`.
- Separates into `pinned` and `extended` (recalled).
- Recalls up to `MEMORY_CONTEXT_LIMIT` (usually 5) via hybrid search.
- Increments usage stats.

## 12. Student Intelligence Readiness
- **Existing Systems**: RAG (document ingestion), Active Documents (PDF viewing/editing), Memory (fact retention).
- **Missing Primitives**: Hierarchical context (Course -> Syllabus -> Assignment). RAG is currently a flat vector search over "personal docs". There is no notion of "Knowledge Scopes" or "Topic Contexts". A Context Engine must introduce scoped context retrieval.

## 13. Provider Coupling
- **Gemini**: Requires `extra_content` (thought_signatures) to be echoed back.
- **DeepSeek/vLLM**: Requires `reasoning_content` to be echoed back for continuity.
- **Anthropic**: Rejects empty `content` blocks.
- **OpenAI/Local**: Strict KV-cache matching requires static system prefixes.
Context assembly logic is heavily littered with provider-specific workarounds.

## 14. Performance Risks
- `MemoryManager.load()` parses the entire `memory.json` file on every single turn.
- RAG search and Web Search happen *inline* in the request thread, blocking TTFT (Time To First Token).
- Repeated token counting (`estimate_tokens`) across the loop.

## 15. Failure Modes
- **RAG failure**: Swallowed (`logger.warning("RAG retrieval failed")`), prompt proceeds without chunks.
- **Web Search failure**: LLM query generation fallback -> uses raw user prompt -> if search fails, swallowed.
- **Context Overflow**: Handled defensively by `context_compactor`, but large tool outputs can blow the budget if `_truncate_text_to_token_budget` limits aren't strict enough per tool.

## 16. Proposed Context Engine Architecture
A new `ContextEngine` should replace scattered assembly.
```text
ContextEngine
├── Scopes
│   ├── UserScope (Preferences, Global Memory)
│   ├── ProjectScope (Workspace, Project Memory, RAG)
│   └── TaskScope (Active Document, Current Turn)
├── Pipeline
│   ├── Gatherers (MemoryGatherer, RagGatherer, WebGatherer) - Run async/parallel
│   ├── Normalizer (Provider-neutral formatting)
│   ├── Budgeter (Token limits, compaction, priority queue)
│   └── Renderer (Output to OpenAI/Anthropic/Gemini format)
```

## 17. Migration Strategy
1. Introduce `ContextEngine` as an optional path.
2. Refactor `chat_processor.build_context_preface` to use the Engine.
3. Fix the `chat_processor` singleton mutation bug immediately.
4. Slowly migrate `_build_base_prompt` out of `agent_loop.py` into the Engine.
5. Standardize tool-result appending via the Engine.

## 18. Files Likely To Change
- `routes/chat_helpers.py`
- `src/chat_processor.py` (Major refactor / deprecation)
- `src/agent_loop.py` (Remove prompt assembly)
- `src/context_budget.py` (Integrate into Engine)
- `src/context_compactor.py` (Integrate into Engine)

## 19. Files That Should NOT Be Changed
- `src/tool_policy.py` / `src/secure_executor.py` (Security boundaries)
- `src/rag_vector.py` (Keep working internals)
- `services/memory/memory.py` (Keep storage mechanics)
- `src/builtin_actions.py` (Tool definitions)

## 20. Risk Assessment
- **Singleton Mutation Leakage**: CRITICAL
- **Context Duplication**: MEDIUM
- **Provider Coupling**: HIGH
- **Performance (Blocking TTFT)**: MEDIUM

---

## TESTING REQUIREMENTS
- **Isolation tests**: Assert concurrent calls to ContextEngine do not share state.
- **Budget/overflow tests**: Assert 200k token tool output is cleanly truncated.
- **Relevance tests**: Assert RAG thresholding drops irrelevant chunks.
- **Reliability tests**: Assert ChromaDB timeout does not crash the chat.
- **Provider compatibility**: Assert Gemini `thought_signatures` and DeepSeek `reasoning_content` format correctly.
- **Student context tests**: Assert scoped knowledge loads cleanly.
