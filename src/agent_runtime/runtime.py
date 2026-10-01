import asyncio
from typing import Optional, Dict, Any, List
from src.agent_runtime.models import AgentRunModel, TaskModel, Plan
from src.agent_runtime.state_machine import AgentState, StateMachine
from src.agent_runtime.persistence import DbTask, DbAgentRun, AgentPersistence
from src.agent_runtime.events import runtime_events, RuntimeEvent
from core.database import SessionLocal
import uuid

class AgentRuntime:
    @staticmethod
    def _emit(event_type: str, run_id: str, payload: dict = None):
        if payload is None:
            payload = {}
        runtime_events.emit(RuntimeEvent(event_type=event_type, run_id=run_id, payload=payload))

    @staticmethod
    def create_run(user_id: str, session_id: str, goal: str, project_id: Optional[str] = None) -> AgentRunModel:
        with SessionLocal() as db:
            task_id = str(uuid.uuid4())
            task = DbTask(id=task_id, user_id=user_id, project_id=project_id, objective=goal)
            db.add(task)
            db.commit()
            
            run_id = str(uuid.uuid4())
            run = DbAgentRun(
                id=run_id, 
                session_id=session_id, 
                user_id=user_id, 
                project_id=project_id, 
                task_id=task_id, 
                goal=goal,
                status=AgentState.CREATED
            )
            db.add(run)
            db.commit()
            
            pydantic_run = AgentPersistence._to_pydantic_run(run)
            AgentRuntime._emit("run.created", run_id, {"goal": goal})
            return pydantic_run

    @staticmethod
    def get_run(run_id: str) -> Optional[AgentRunModel]:
        with SessionLocal() as db:
            run = db.query(DbAgentRun).filter_by(id=run_id).first()
            if not run:
                return None
            return AgentPersistence._to_pydantic_run(run)

    @staticmethod
    def _advance_state(db, run: DbAgentRun, new_state: AgentState, payload: dict = None):
        StateMachine.validate_transition(run.status, new_state)
        run.status = new_state
        db.commit()
        AgentRuntime._emit("run.state_changed", run.id, {"new_state": new_state, "payload": payload or {}})

    @staticmethod
    async def start_run(run_id: str):
        AgentRuntime._emit("run.started", run_id)
        
        with SessionLocal() as db:
            db_run = db.query(DbAgentRun).filter_by(id=run_id).first()
            if not db_run:
                raise ValueError("Run not found")
            
            # Transition to UNDERSTANDING
            AgentRuntime._advance_state(db, db_run, AgentState.UNDERSTANDING)
            
            # ContextEngine integration
            try:
                from src.context_engine.engine import ContextEngine
                from src.context_engine.models import ContextRequest
                engine = ContextEngine([])
                req = ContextRequest(owner=db_run.user_id, session_id=db_run.session_id)
                ctx = await engine.build_context(req, model="default")
                AgentRuntime._emit("context.prepared", run_id, {"messages_count": len(ctx.get("messages", []))})
            except Exception as e:
                AgentRuntime._emit("context.prepared", run_id, {"error": str(e)})

            # Provider Intelligence integration
            try:
                from src.foreground_model_routing import resolve_foreground_model_policy
                url, model_name = resolve_foreground_model_policy(owner=db_run.user_id)
                db_run.selected_provider = url
                db_run.selected_model = model_name
                db.commit()
                AgentRuntime._emit("model.selected", run_id, {"provider": url, "model": model_name})
            except Exception as e:
                # Mock or fallback if fails in test environment
                db_run.selected_model = "fallback-model"
                db.commit()
                AgentRuntime._emit("model.selected", run_id, {"model": "fallback-model", "error": str(e)})
                model_name = "fallback-model"

            # Transition to PLANNING
            AgentRuntime._advance_state(db, db_run, AgentState.PLANNING)
            # In a real impl, we'd call the model here. For step 2, we just transition forward.
            
            AgentRuntime._advance_state(db, db_run, AgentState.READY)
            AgentRuntime._advance_state(db, db_run, AgentState.WAITING_FOR_MODEL)
            
            AgentRuntime._emit("model.started", run_id, {"model": model_name})
            
            # Simulate a model response that produces a tool request
            # Step 2 strictly requires STOPPING safely here before execution
            db_run.current_tool_call = {"tool": "search", "query": "fusion"}
            db.commit()
            
            AgentRuntime._advance_state(db, db_run, AgentState.MODEL_PRODUCED_TOOL)
            AgentRuntime._emit("model.completed", run_id)
            AgentRuntime._emit("tool.pending", run_id, {"tool": "search"})
            
            # Stop safely at the boundary as per Phase 5B Step 2 requirements
            # We do NOT execute the tool.

    @staticmethod
    def cancel_run(run_id: str):
        with SessionLocal() as db:
            run = db.query(DbAgentRun).filter_by(id=run_id).first()
            if not run:
                raise ValueError("Run not found")
            StateMachine.validate_transition(run.status, AgentState.CANCELLED)
            run.status = AgentState.CANCELLED
            db.commit()
            AgentRuntime._emit("run.cancelled", run_id)
