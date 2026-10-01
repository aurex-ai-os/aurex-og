import pytest
from src.executor.registry import (
    ToolRegistry, ToolDefinition, Capability, ToolCall,
    DuplicateToolError, ToolNotFoundError
)
from src.executor.policy import PolicyEngine
from src.executor.models import DecisionType

def test_tool_registration():
    registry = ToolRegistry()
    tdef = ToolDefinition(
        tool_id="test_tool",
        name="Test",
        description="A test tool",
        capabilities=[Capability.READ_ONLY]
    )
    registry.register(tdef)
    assert len(registry.list_tools()) == 1
    
    with pytest.raises(DuplicateToolError):
        registry.register(tdef)
        
    assert registry.resolve("test_tool").name == "Test"
    
    with pytest.raises(ToolNotFoundError):
        registry.resolve("missing")

def test_schema_generation():
    registry = ToolRegistry()
    registry.register(ToolDefinition(
        tool_id="demo",
        name="Demo",
        description="Demo tool",
        input_schema={"type": "object", "properties": {"a": {"type": "string"}}}
    ))
    schemas = registry.get_model_tools()
    assert len(schemas) == 1
    assert schemas[0]["function"]["name"] == "demo"
    assert schemas[0]["function"]["parameters"]["properties"]["a"]["type"] == "string"

def test_policy_read_only(tmp_path):
    policy = PolicyEngine(str(tmp_path))
    tdef = ToolDefinition(
        tool_id="ro", name="RO", description="RO",
        capabilities=[Capability.READ_ONLY]
    )
    call = ToolCall(call_id="1", tool_id="ro", arguments={})
    dec = policy.evaluate_tool_call(call, tdef)
    assert dec.decision == DecisionType.ALLOW

def test_policy_process_execution(tmp_path):
    policy = PolicyEngine(str(tmp_path))
    tdef = ToolDefinition(
        tool_id="exec", name="Exec", description="Exec",
        capabilities=[Capability.PROCESS_EXECUTION]
    )
    call = ToolCall(call_id="1", tool_id="exec", arguments={})
    dec = policy.evaluate_tool_call(call, tdef)
    assert dec.decision == DecisionType.ASK

def test_policy_mcp_execution(tmp_path):
    policy = PolicyEngine(str(tmp_path))
    tdef = ToolDefinition(
        tool_id="mcp", name="MCP", description="MCP",
        capabilities=[Capability.MCP_EXECUTION]
    )
    call = ToolCall(call_id="1", tool_id="mcp", arguments={})
    dec = policy.evaluate_tool_call(call, tdef)
    assert dec.decision == DecisionType.ASK
