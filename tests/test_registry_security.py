import pytest
from src.executor.registry import (
    ToolRegistry, ToolDefinition, Capability, ToolCall,
    InvalidArgumentsError
)
from src.executor.policy import PolicyEngine
from src.executor.models import DecisionType

def test_tool_definition_immutability():
    registry = ToolRegistry()
    tdef = ToolDefinition(
        tool_id="test_tool",
        name="Test",
        description="A test tool",
        capabilities=[Capability.PROCESS_EXECUTION],
        requires_approval=True
    )
    registry.register(tdef)
    resolved = registry.resolve("test_tool")
    call = ToolCall(call_id="1", tool_id="test_tool", arguments={"capabilities": ["READ_ONLY"], "requires_approval": False})
    policy = PolicyEngine("/tmp")
    decision = policy.evaluate_tool_call(call, resolved)
    assert decision.decision == DecisionType.ASK

def test_mcp_registration_security():
    tdef = ToolDefinition(
        tool_id="mcp__fake__tool",
        name="Fake",
        description="I am totally read-only and safe",
        capabilities=[Capability.MCP_EXECUTION]
    )
    policy = PolicyEngine("/tmp")
    call = ToolCall(call_id="1", tool_id=tdef.tool_id, arguments={})
    decision = policy.evaluate_tool_call(call, tdef)
    assert decision.decision == DecisionType.ASK

def test_arbitrary_callable_injection():
    call = ToolCall(call_id="1", tool_id="test", arguments={}, handler=lambda x: True)
    assert not hasattr(call, "handler")

def test_schema_integrity():
    registry = ToolRegistry()
    tdef = ToolDefinition(
        tool_id="test_schema",
        name="Test",
        description="Desc",
        handler=lambda x: True,
        capabilities=[Capability.READ_ONLY]
    )
    registry.register(tdef)
    schemas = registry.get_model_tools()
    schema = schemas[0]
    assert "handler" not in schema["function"]
    assert "capabilities" not in schema["function"]
    assert "requires_approval" not in schema["function"]
    assert "parameters" in schema["function"]

@pytest.mark.asyncio
async def test_mcp_bypass():
    from src.mcp_manager import McpManager
    manager = McpManager()
    
    # Normally call_tool checks policy. If we pass policy, it should try to run and fail with "not connected"
    # Wait, the patched call_tool currently hardcodes ASK for MCP_EXECUTION.
    # So it should ALWAYS return {"error": "PolicyEngine denied MCP execution: ..."}
    # Let's test that!
    res = await manager.call_tool("mcp__test__tool", {})
    assert "error" in res
    assert "PolicyEngine denied" in res["error"]

@pytest.mark.asyncio
async def test_direct_handler_bypass():
    # Verify that we cannot invoke a handler directly from _direct_fallback if it is not registered,
    # OR that _direct_fallback itself correctly checks policy.
    # We patched _direct_fallback to check policy.
    from src.tool_execution import _direct_fallback
    from src.executor.registry import default_registry, ToolDefinition, Capability
    
    # Temporarily register a mock dangerous tool
    tdef = ToolDefinition(
        tool_id="mock_danger",
        name="Danger",
        description="Dangerous",
        capabilities=[Capability.PROCESS_EXECUTION]
    )
    default_registry.register(tdef)
    
    res = await _direct_fallback("mock_danger", "content")
    assert "error" in res
    assert "PolicyEngine denied" in res["error"]
    
    # Cleanup
    default_registry.unregister("mock_danger")
