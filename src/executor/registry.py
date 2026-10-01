import json
import logging
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Callable, Awaitable

logger = logging.getLogger(__name__)

class Capability(str, Enum):
    READ_ONLY = "READ_ONLY"
    FILESYSTEM_READ = "FILESYSTEM_READ"
    FILESYSTEM_WRITE = "FILESYSTEM_WRITE"
    FILESYSTEM_DELETE = "FILESYSTEM_DELETE"
    PROCESS_EXECUTION = "PROCESS_EXECUTION"
    NETWORK_ACCESS = "NETWORK_ACCESS"
    CREDENTIAL_ACCESS = "CREDENTIAL_ACCESS"
    EXTERNAL_SERVICE = "EXTERNAL_SERVICE"
    MCP_EXECUTION = "MCP_EXECUTION"

class ToolDefinition(BaseModel):
    tool_id: str
    name: str
    description: str
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    capabilities: List[Capability] = Field(default_factory=list)
    requires_approval: bool = False
    handler: Any = None

class ToolCall(BaseModel):
    call_id: str
    tool_id: str
    arguments: Dict[str, Any]

class ToolResult(BaseModel):
    success: bool
    content: str
    error: Optional[str] = None
    structured_data: Optional[Dict] = None
    call_id: Optional[str] = None

class ToolRegistryError(Exception): pass
class ToolNotFoundError(ToolRegistryError): pass
class DuplicateToolError(ToolRegistryError): pass
class InvalidArgumentsError(ToolRegistryError): pass

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        
    def register(self, tool_def: ToolDefinition):
        if tool_def.tool_id in self._tools:
            raise DuplicateToolError(f"Tool {tool_def.tool_id} already registered.")
        self._tools[tool_def.tool_id] = tool_def
        
    def unregister(self, tool_id: str):
        if tool_id in self._tools:
            del self._tools[tool_id]
            
    def resolve(self, tool_id: str) -> ToolDefinition:
        if tool_id not in self._tools:
            raise ToolNotFoundError(f"Tool {tool_id} not found.")
        return self._tools[tool_id]
        
    def list_tools(self) -> List[ToolDefinition]:
        return list(self._tools.values())
        
    def get_model_tools(self) -> List[Dict[str, Any]]:
        # Outputs an OpenAI-compatible function schema array
        result = []
        for t in self._tools.values():
            if t.input_schema:
                schema = t.input_schema
            else:
                # Default minimal schema if not provided
                schema = {
                    "type": "object",
                    "properties": {"content": {"type": "string", "description": "Raw string argument for the tool"}},
                    "required": ["content"]
                }
            result.append({
                "type": "function",
                "function": {
                    "name": t.tool_id,
                    "description": t.description,
                    "parameters": schema
                }
            })
        return result

# Global default registry
default_registry = ToolRegistry()
