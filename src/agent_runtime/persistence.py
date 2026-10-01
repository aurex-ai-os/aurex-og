import json
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, JSON, Enum, Text
from sqlalchemy.orm import relationship
from core.database import Base, TimestampMixin, utcnow_naive
from src.agent_runtime.state_machine import AgentState
from src.agent_runtime.models import AgentRunModel, Plan, ArtifactReference, TaskModel

class DbTask(TimestampMixin, Base):
    __tablename__ = "agent_tasks"
    
    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    project_id = Column(String, nullable=True, index=True)
    objective = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="pending")
    metadata_ = Column("metadata", JSON, nullable=True)

class DbAgentRun(TimestampMixin, Base):
    __tablename__ = "agent_runs"
    
    id = Column(String, primary_key=True)
    session_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    project_id = Column(String, nullable=True, index=True)
    task_id = Column(String, ForeignKey("agent_tasks.id"), nullable=False, index=True)
    parent_run_id = Column(String, nullable=True)
    
    goal = Column(Text, nullable=False)
    status = Column(Enum(AgentState), nullable=False, default=AgentState.CREATED)
    iteration = Column(Integer, nullable=False, default=0)
    
    plan = Column(JSON, nullable=True)
    current_step = Column(String, nullable=True)
    context_reference = Column(String, nullable=True)
    
    selected_model = Column(String, nullable=True)
    selected_provider = Column(String, nullable=True)
    model_role = Column(String, nullable=True)
    
    pending_approval = Column(JSON, nullable=True)
    current_tool_call = Column(JSON, nullable=True)
    tool_calls = Column(JSON, nullable=True)
    observations = Column(JSON, nullable=True)
    artifacts = Column(JSON, nullable=True)
    
    started_at = Column(DateTime, nullable=False, default=utcnow_naive)
    completed_at = Column(DateTime, nullable=True)
    
    failure = Column(Text, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    verification_result = Column(JSON, nullable=True)
    metadata_ = Column("metadata", JSON, nullable=True)
    
    # Optimistic concurrency control version
    version = Column(Integer, nullable=False, default=1)
    
    __mapper_args__ = {
        "version_id_col": version
    }

class AgentPersistence:
    @staticmethod
    def _to_pydantic_run(db_run: DbAgentRun) -> AgentRunModel:
        return AgentRunModel(
            run_id=db_run.id,
            session_id=db_run.session_id,
            user_id=db_run.user_id,
            project_id=db_run.project_id,
            task_id=db_run.task_id,
            parent_run_id=db_run.parent_run_id,
            goal=db_run.goal,
            status=db_run.status,
            iteration=db_run.iteration,
            plan=Plan(**db_run.plan) if db_run.plan else None,
            current_step=db_run.current_step,
            context_reference=db_run.context_reference,
            selected_model=db_run.selected_model,
            selected_provider=db_run.selected_provider,
            model_role=db_run.model_role,
            pending_approval=db_run.pending_approval,
            current_tool_call=db_run.current_tool_call,
            tool_calls=db_run.tool_calls or [],
            observations=db_run.observations or [],
            artifacts=[ArtifactReference(**a) for a in (db_run.artifacts or [])],
            started_at=db_run.started_at,
            updated_at=db_run.updated_at,
            completed_at=db_run.completed_at,
            failure=db_run.failure,
            cancellation_reason=db_run.cancellation_reason,
            verification_result=db_run.verification_result,
            metadata=db_run.metadata_ or {},
            version=db_run.version
        )

    @staticmethod
    def _update_db_run(db_run: DbAgentRun, model: AgentRunModel) -> None:
        db_run.status = model.status
        db_run.iteration = model.iteration
        db_run.plan = model.plan.model_dump() if model.plan else None
        db_run.current_step = model.current_step
        db_run.context_reference = model.context_reference
        db_run.selected_model = model.selected_model
        db_run.selected_provider = model.selected_provider
        db_run.model_role = model.model_role
        
        # Don't persist secrets (filtering happens before here ideally, but enforcing it at DB layer)
        if model.pending_approval:
            db_run.pending_approval = AgentPersistence._scrub_secrets(model.pending_approval)
        else:
            db_run.pending_approval = None
            
        db_run.current_tool_call = AgentPersistence._scrub_secrets(model.current_tool_call) if model.current_tool_call else None
        db_run.tool_calls = [AgentPersistence._scrub_secrets(tc) for tc in model.tool_calls]
        db_run.observations = model.observations
        db_run.artifacts = [a.model_dump() for a in model.artifacts]
        
        db_run.completed_at = model.completed_at
        db_run.failure = model.failure
        db_run.cancellation_reason = model.cancellation_reason
        db_run.verification_result = model.verification_result
        db_run.metadata_ = model.metadata

    @staticmethod
    def _scrub_secrets(data: dict) -> dict:
        """Removes explicit secrets, api_keys, authorization headers before persisting"""
        if not data:
            return data
        scrubbed = data.copy()
        for k in list(scrubbed.keys()):
            k_lower = k.lower()
            if "secret" in k_lower or "api_key" in k_lower or "authorization" in k_lower or "password" in k_lower:
                scrubbed[k] = "***SCRUBBED***"
            elif isinstance(scrubbed[k], dict):
                scrubbed[k] = AgentPersistence._scrub_secrets(scrubbed[k])
        return scrubbed
