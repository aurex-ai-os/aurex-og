from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from src.agent_runtime.state_machine import AgentState

class ArtifactReference(BaseModel):
    artifact_id: str
    run_id: str
    project_id: Optional[str] = None
    type: str
    name: str
    path: str
    version: int = 1
    created_at: datetime
    source_references: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class PlanStep(BaseModel):
    step_id: str
    description: str
    status: str = "pending"
    dependencies: List[str] = Field(default_factory=list)
    required_capabilities: List[str] = Field(default_factory=list)
    tool_candidates: List[str] = Field(default_factory=list)
    result: Optional[str] = None
    failure: Optional[str] = None

class Plan(BaseModel):
    steps: List[PlanStep] = Field(default_factory=list)

class AgentRunModel(BaseModel):
    run_id: str
    session_id: str
    user_id: str
    project_id: Optional[str] = None
    task_id: str
    parent_run_id: Optional[str] = None
    
    goal: str
    status: AgentState
    iteration: int = 0
    
    plan: Optional[Plan] = None
    current_step: Optional[str] = None
    context_reference: Optional[str] = None
    
    selected_model: Optional[str] = None
    selected_provider: Optional[str] = None
    model_role: Optional[str] = None
    
    pending_approval: Optional[Dict[str, Any]] = None
    current_tool_call: Optional[Dict[str, Any]] = None
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    observations: List[Dict[str, Any]] = Field(default_factory=list)
    artifacts: List[ArtifactReference] = Field(default_factory=list)
    
    started_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    
    failure: Optional[str] = None
    cancellation_reason: Optional[str] = None
    verification_result: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    version: int = 1

class TaskModel(BaseModel):
    task_id: str
    user_id: str
    project_id: Optional[str] = None
    objective: str
    status: str
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)
