from typing import Any, Dict, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from core.database import utcnow_naive

class RuntimeEvent(BaseModel):
    event_type: str
    run_id: str
    timestamp: datetime = Field(default_factory=utcnow_naive)
    payload: Dict[str, Any] = Field(default_factory=dict)

class EventEmitter:
    def __init__(self):
        self.handlers = []
        
    def add_handler(self, handler):
        self.handlers.append(handler)
        
    def emit(self, event: RuntimeEvent):
        for handler in self.handlers:
            try:
                handler(event)
            except Exception as e:
                # Log but don't fail the execution
                import logging
                logging.getLogger(__name__).error(f"Event handler failed: {e}")

# Global event bus for the runtime
runtime_events = EventEmitter()
