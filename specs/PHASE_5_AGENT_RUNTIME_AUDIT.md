# Phase 5: Native Agent Runtime Audit

## 1. Existing Agent/Chat/Model Execution Path
- **Entry Point:** `routes/chat_routes.py` and `routes/chat_routes_stream.py` handle chat loop.
- **Model Invocation:** `core/models.py` or specific provider logic invokes models directly.
- **Execution Loop:** Request/response loop where tools are identified and called.

## 2. Reusable Infrastructure
- **SecureExecutor & PolicyEngine:** Existing in `create_executor.py` and policy patches.
- **Provider Intelligence:** Exists in `services/providers.py` or `services/hardware/`.
- **Context Engine:** Existing `services/memory/` and `mcp_servers/rag_server.py`.
- **ToolRegistry:** Existing MCP integration and `patch_tools.py`.

## 3. Duplicate Orchestration Logic
- Likely found in multiple route files (`chat_routes.py`, `research_routes.py`, `task_routes.py`) implementing their own variants of prompting and tool execution.

## 4. Direct Model/Tool Invocations
- Chat endpoints directly invoke LLMs, and when a tool is requested, it directly runs in the HTTP request lifecycle or background task (e.g., `patch_tool_exec_bg.py`).

## 5. Existing Approval Mechanisms
- **Ghost Sessions & Approval:** `core/models.py` uses `CHAT_SESSION_APPROVAL_DECISION` and `ApprovalRequired` exception in `create_executor.py`.

## 6. Existing SSE/Event Mechanisms
- `routes/chat_routes_stream.py` and SSE broadcasting are used to push UI updates.

## 7. Session/Task Persistence
- SQLite database via SQLAlchemy (`core/database.py`, `core/session_manager.py`). Sessions are saved, but tasks are not explicitly managed with `AgentRun` states.

## 8. Artifact/Document Creation Paths
- Exists partially in `routes/document_routes.py` and file/workspace tools, but lacks a canonical artifact graph.

## 9. Cancellation Mechanisms
- Incomplete. Some basic background job cancellation might exist (`patch_bg_jobs.py`), but true agent termination is lacking.

## Conclusion
The foundation is highly capable, but requires a central state machine (`AgentRun`) in `src/agent_runtime/` to orchestrate Context, Provider Intelligence, Tools, and Approvals deterministically.
