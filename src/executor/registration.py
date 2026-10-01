from .registry import default_registry, ToolDefinition, Capability
from src.agent_tools import TOOL_HANDLERS
from src.tool_schemas import FUNCTION_TOOL_SCHEMAS
import logging

logger = logging.getLogger(__name__)

def bootstrap_registry():
    """Populates the ToolRegistry with existing Aurex capabilities."""
    
    # Pre-defined capabilities mapping for known native tools
    tool_capabilities = {
        "bash": [Capability.PROCESS_EXECUTION, Capability.FILESYSTEM_READ, Capability.FILESYSTEM_WRITE],
        "python": [Capability.PROCESS_EXECUTION, Capability.FILESYSTEM_READ, Capability.FILESYSTEM_WRITE],
        "web_search": [Capability.NETWORK_ACCESS, Capability.READ_ONLY],
        "web_fetch": [Capability.NETWORK_ACCESS, Capability.READ_ONLY],
        "read_file": [Capability.FILESYSTEM_READ],
        "write_file": [Capability.FILESYSTEM_WRITE],
        "edit_file": [Capability.FILESYSTEM_WRITE, Capability.FILESYSTEM_READ],
        "apply_patch": [Capability.FILESYSTEM_WRITE, Capability.FILESYSTEM_READ],
        "todowrite": [Capability.FILESYSTEM_WRITE],
        "ls": [Capability.FILESYSTEM_READ],
        "glob": [Capability.FILESYSTEM_READ],
        "grep": [Capability.FILESYSTEM_READ],
        "create_document": [Capability.READ_ONLY],  # Document tools don't map perfectly to FS mutations yet
        "update_document": [Capability.READ_ONLY],
        "edit_document": [Capability.READ_ONLY],
        "suggest_document": [Capability.READ_ONLY],
        "manage_documents": [Capability.READ_ONLY],
        "get_workspace": [Capability.READ_ONLY],
        "ask_user": [Capability.READ_ONLY],
        "update_plan": [Capability.READ_ONLY],
        "chat_with_model": [Capability.EXTERNAL_SERVICE],
        "ask_teacher": [Capability.EXTERNAL_SERVICE],
        "list_models": [Capability.READ_ONLY],
        "manage_bg_jobs": [Capability.PROCESS_EXECUTION],
        "create_session": [Capability.READ_ONLY],
        "list_sessions": [Capability.READ_ONLY],
        "send_to_session": [Capability.READ_ONLY],
        "manage_session": [Capability.READ_ONLY],
    }

    # Map LLM schemas
    schemas_by_name = {schema["function"]["name"]: schema["function"].get("parameters", {}) for schema in FUNCTION_TOOL_SCHEMAS if "function" in schema}

    for tool_id, handler in TOOL_HANDLERS.items():
        caps = tool_capabilities.get(tool_id, [Capability.READ_ONLY])
        schema = schemas_by_name.get(tool_id, {})
        
        # In this phase, we map directly to the original coroutine handler 
        # so tool_execution can execute it if policy passes.
        tdef = ToolDefinition(
            tool_id=tool_id,
            name=tool_id.replace("_", " ").title(),
            description=next((s["function"].get("description", f"Legacy tool {tool_id}") for s in FUNCTION_TOOL_SCHEMAS if "function" in s and s["function"]["name"] == tool_id), f"Legacy tool {tool_id}"),
            input_schema=schema,
            capabilities=caps,
            requires_approval=True if Capability.PROCESS_EXECUTION in caps else False,
            handler=handler
        )
        try:
            default_registry.register(tdef)
        except Exception as e:
            logger.warning(f"Skipping registry for {tool_id}: {e}")

