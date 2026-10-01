
from enum import Enum
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

class DecisionType(str, Enum):
    ALLOW = "ALLOW"
    PREVIEW = "PREVIEW"
    ASK = "ASK"
    FORBIDDEN = "FORBIDDEN"

class ExecutionRequest(BaseModel):
    operation_type: str
    arguments: Dict[str, Any]
    working_directory: Optional[str] = None
    requested_permissions: List[str] = []
    origin_tool: str = "unknown"
    task_id: Optional[str] = None

class ExecutionDecision(BaseModel):
    decision: DecisionType
    reason: str

class ApprovedAction:
    def __init__(self, request: ExecutionRequest, decision: ExecutionDecision):
        if decision.decision not in (DecisionType.ALLOW, DecisionType.PREVIEW):
            raise ValueError(f"Cannot create ApprovedAction from {decision.decision} decision")
        # Store immutable copies to prevent post-approval mutation
        self._request = request.model_copy(deep=True)
        self._decision = decision.model_copy(deep=True)
        self._is_approved = True
        
    @property
    def request(self) -> ExecutionRequest:
        return self._request.model_copy(deep=True)
        
    @property
    def decision(self) -> ExecutionDecision:
        return self._decision.model_copy(deep=True)
