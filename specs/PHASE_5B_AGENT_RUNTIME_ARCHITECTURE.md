# Phase 5B Native Agent Runtime Architecture

## 1. Deep Execution-Path Audit

### Current Legacy Execution Path
The current application relies heavily on `routes/chat_routes.py` acting as the entry point, routing to `src/agent_loop.py` (`stream_agent_loop`).
1. **User Request:** Arrives at `/api/chat_stream`
2. **Context Gathering:** Inline history aggregation and Context Budgeting (`maybe_compact`)
3. **Model Routing:** Handled by `resolve_foreground_model_policy()` inside the HTTP route.
4. **Agent Loop:** Calls `stream_llm` in a `while` loop (`src/agent_loop.py`).
5. **Tool Execution:** Parses fenced code blocks. Tools are instantiated directly. Subprocess tools are intercepted via `patch_tools.py` to use `SecureExecutor` and `PolicyEngine`.
6. **Approval:** Wait-for-approval uses `ApprovalRequired` raising exceptions or specific chat markers.
7. **Streaming:** Yields raw JSON events directly to the HTTP SSE Response.

**Observations:** Orchestration is coupled to the HTTP request lifecycle. Models are invoked directly without an abstraction for 'Task' vs 'Run'. Tool execution is scattered across `patch_tools.py`, `patch_agent_loop.py`, and inline definitions.

### Target Execution Path (Native Agent Runtime)
The new `AgentRun` becomes the canonical orchestrator in `src/agent_runtime/runtime.py`.
1. **User Request:** `routes/chat_routes.py` translates the request into `create_run()` and `start_run()`.
2. **UNDERSTANDING / PLANNING:** Runtime assesses task and builds a structured plan.
3. **CONTEXT:** Iteratively uses `ContextEngine` via `agent_runtime/observer.py`.
4. **MODEL SELECTION:** Delegates to `Provider Intelligence`.
5. **EXECUTION:** Model produces action -> `ToolRegistry` -> `PolicyEngine`.
6. **APPROVAL:** If `PolicyEngine` returns `ASK`, state -> `WAITING_FOR_APPROVAL` (and runtime pauses natively).
7. **VERIFICATION:** Verifies outputs before `COMPLETED`.
8. **SSE / UI:** Uses `agent_runtime/events.py` which emits canonical `run.*` events that `chat_routes_stream.py` simply listens to and forwards.

## 2. Runtime Components
* **`runtime.py`**: Exposes `create_run`, `start_run`, `pause_run`, `resume_run`, `cancel_run`.
* **`planner.py`**: Translates goals into structured `Plan` utilizing the Pydantic models.
* **`model_runner.py`**: Interacts with `Provider Intelligence` for selection and parsing structural output.
* **`tool_runner.py`**: Handles `ToolRegistry` -> `PolicyEngine` -> `SecureExecutor` pipeline and handles `ASK` flows.
* **`observer.py`**: Synthesizes `ToolResult` into `Observation` records.
* **`verifier.py`**: Evaluates `COMPLETED` conditions.
* **`events.py`**: canonical structured event emitter (`run.started`, `run.tool_requested`).

## 3. Migration Strategy
1. Build the components in `src/agent_runtime/`.
2. Integrate ContextEngine, ProviderIntelligence, PolicyEngine.
3. Write isolated runtime tests (40+).
4. Do NOT replace `/api/chat_stream` immediately. Implement a `/api/v2/agent_run` endpoint or shim for agentic tasks.
