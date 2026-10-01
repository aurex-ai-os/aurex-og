from dataclasses import dataclass
from typing import Optional

@dataclass
class ScopedContext:
    """Explicit isolation boundaries for context retrieval."""
    user_id: Optional[str]
    session_id: Optional[str]
    workspace: Optional[str]
    course_id: Optional[str] = None  # Future Student Intelligence
