# OMNIROUTE + FREELLMAPI ARCHITECTURE

## 1. Overview
Aurex natively integrates OmniRoute and FreeLLMAPI not as chained gateways, but as **Provider Pools**. Aurex remains the primary routing authority and enforces strict context admission, capability matching, and fallback strategies.

## 2. Core Components

### Provider Pools (`src/provider_intelligence/provider_pools.py`)
- Adapters for OmniRoute and FreeLLMAPI implement a shared interface.
- Models fetched from pools carry `metadata_confidence` and `metadata_source` attributes, ensuring Aurex knows exactly where claims originated.
- All credentials route through `SecretStorage`.

### Context Engine (`src/context_engine/`)
- **Context Admission:** Estimates tokens via `tiktoken` (cl100k_base) or fallback heuristics. Enforces a 92% safe boundary against verified model limits.
- **Context Waterfall:** Progressively reduces payloads through 9 strategies: dedup, system trim, old message summarization, sliding window, tool output truncation, and subtask splitting.
- **Error Recovery:** Classifies errors (e.g. `CONTEXT_OVERFLOW`, `RATE_LIMIT`) and drives structured retries with exponential backoff. Prevents retry storms and guarantees `CONTEXT_OVERFLOW` never retries the same raw payload.

### Routing Engine (`src/provider_intelligence/routing_engine.py`)
- Explains routing decisions via explicit `reason_codes`.
- Considers hard capability sets (vision, tool calling, local execution), health status, reliability scores, and verifies the context window can hold the incoming prompt.

### Token Ledger (`src/token_ledger.py`)
- Unified SQLite-based token accounting across all pools and providers.
- Records token counts, compression savings, latency, and error rates.
- Never logs API keys or raw prompts.

### Large Task Processor (`src/large_task_processor.py`)
- Bounded 8-stage Map/Chunk/Analyze/Store/Retrieve/CrossReference/Synthesize/Verify pipeline.
- Safely processes massive document sets without overflowing context limits.

### Tool Observation Store (`src/tool_observation_store.py`)
- Enormous tool outputs are saved directly to disk.
- Injects a context-safe summary (under 800 chars) into the conversation history, protecting downstream context.
