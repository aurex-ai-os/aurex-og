from enum import Enum
from typing import Dict, Set

class AgentState(str, Enum):
    CREATED = "CREATED"
    UNDERSTANDING = "UNDERSTANDING"
    PLANNING = "PLANNING"
    READY = "READY"
    WAITING_FOR_MODEL = "WAITING_FOR_MODEL"
    MODEL_PRODUCED_TOOL = "MODEL_PRODUCED_TOOL"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    EXECUTING_TOOL = "EXECUTING_TOOL"
    TOOL_COMPLETED = "TOOL_COMPLETED"
    OBSERVING = "OBSERVING"
    REPLANNING = "REPLANNING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PAUSED = "PAUSED"
    WAITING_FOR_USER = "WAITING_FOR_USER"

class InvalidStateTransitionError(Exception):
    pass

class StateMachine:
    VALID_TRANSITIONS: Dict[AgentState, Set[AgentState]] = {
        AgentState.CREATED: {AgentState.UNDERSTANDING, AgentState.PLANNING, AgentState.READY, AgentState.CANCELLED},
        AgentState.UNDERSTANDING: {AgentState.PLANNING, AgentState.READY, AgentState.FAILED, AgentState.CANCELLED},
        AgentState.PLANNING: {AgentState.READY, AgentState.FAILED, AgentState.CANCELLED},
        AgentState.READY: {AgentState.WAITING_FOR_MODEL, AgentState.COMPLETED, AgentState.FAILED, AgentState.CANCELLED, AgentState.WAITING_FOR_USER},
        AgentState.WAITING_FOR_MODEL: {AgentState.READY, AgentState.MODEL_PRODUCED_TOOL, AgentState.FAILED, AgentState.CANCELLED},
        AgentState.MODEL_PRODUCED_TOOL: {AgentState.WAITING_FOR_APPROVAL, AgentState.EXECUTING_TOOL, AgentState.FAILED, AgentState.CANCELLED},
        AgentState.WAITING_FOR_APPROVAL: {AgentState.EXECUTING_TOOL, AgentState.REPLANNING, AgentState.FAILED, AgentState.CANCELLED, AgentState.PAUSED},
        AgentState.EXECUTING_TOOL: {AgentState.TOOL_COMPLETED, AgentState.FAILED, AgentState.CANCELLED},
        AgentState.TOOL_COMPLETED: {AgentState.OBSERVING, AgentState.FAILED, AgentState.CANCELLED},
        AgentState.OBSERVING: {AgentState.REPLANNING, AgentState.VERIFYING, AgentState.READY, AgentState.FAILED, AgentState.CANCELLED},
        AgentState.REPLANNING: {AgentState.READY, AgentState.FAILED, AgentState.CANCELLED},
        AgentState.VERIFYING: {AgentState.COMPLETED, AgentState.REPLANNING, AgentState.FAILED, AgentState.CANCELLED},
        AgentState.WAITING_FOR_USER: {AgentState.READY, AgentState.CANCELLED, AgentState.FAILED},
        AgentState.PAUSED: {AgentState.WAITING_FOR_APPROVAL, AgentState.READY, AgentState.CANCELLED},
        AgentState.COMPLETED: set(),
        AgentState.FAILED: set(),
        AgentState.CANCELLED: set(),
    }

    @classmethod
    def validate_transition(cls, current: AgentState, next_state: AgentState) -> None:
        if next_state not in cls.VALID_TRANSITIONS.get(current, set()):
            raise InvalidStateTransitionError(f"Cannot transition from {current} to {next_state}")

    @classmethod
    def can_transition(cls, current: AgentState, next_state: AgentState) -> bool:
        return next_state in cls.VALID_TRANSITIONS.get(current, set())

    @classmethod
    def is_terminal(cls, state: AgentState) -> bool:
        return state in {AgentState.COMPLETED, AgentState.FAILED, AgentState.CANCELLED}
