from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class ContextScope(str, Enum):
    SYSTEM = "system"
    USER = "user"
    PROJECT = "project"
    TASK = "task"
    COURSE = "course"  # Future Student Intelligence Scope

class ContextSource(str, Enum):
    SYSTEM_PROMPT = "system_prompt"
    CONVERSATION_HISTORY = "conversation_history"
    ACTIVE_DOCUMENT = "active_document"
    MEMORY = "memory"
    RAG = "rag"
    WEB_SEARCH = "web_search"
    TOOL_OUTPUT = "tool_output"
    USER_PREFERENCE = "user_preference"
    WORKSPACE_RULES = "workspace_rules"
    SKILL = "skill"
    FILE_UPLOAD = "file_upload"

class ContextItem(BaseModel):
    id: str
    source: ContextSource
    scope: ContextScope
    content: str
    priority: int = 50
    relevance: float = 1.0
    token_estimate: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: float = 0.0
    deduplication_key: Optional[str] = None

class ContextRequest(BaseModel):
    owner: Optional[str] = None
    session_id: Optional[str] = None
    message: str = ""
    workspace: Optional[str] = None
    active_document_id: Optional[str] = None
    time_filter: Optional[str] = None
    use_web: bool = False
    use_rag: bool = True
    use_memory: bool = True
    use_skills: bool = True
    preset_system_prompt: Optional[str] = None
    character_name: Optional[str] = None
    agent_mode: bool = False
    incognito: bool = False
    # Additional state can be passed here
