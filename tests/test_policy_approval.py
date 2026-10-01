from src.executor.policy import PolicyEngine
from src.executor.registry import ToolDefinition, Capability, ToolCall
from src.executor.models import DecisionType

def test_requires_approval_constraint():
    policy = PolicyEngine("/tmp")
    
    # 1. READ_ONLY normally allowed
    tdef_allow = ToolDefinition(tool_id="t1", name="t", description="t", capabilities=[Capability.READ_ONLY], requires_approval=False)
    call = ToolCall(call_id="1", tool_id="t1", arguments={})
    assert policy.evaluate_tool_call(call, tdef_allow).decision == DecisionType.ALLOW
    
    # 2. requires_approval=True bumps ALLOW to ASK
    tdef_ask = ToolDefinition(tool_id="t2", name="t", description="t", capabilities=[Capability.READ_ONLY], requires_approval=True)
    call2 = ToolCall(call_id="2", tool_id="t2", arguments={})
    assert policy.evaluate_tool_call(call2, tdef_ask).decision == DecisionType.ASK
    
    # 3. requires_approval=False does NOT downgrade FORBIDDEN
    tdef_forbidden = ToolDefinition(tool_id="t3", name="t", description="t", capabilities=[Capability.FILESYSTEM_WRITE], requires_approval=False)
    call3 = ToolCall(call_id="3", tool_id="t3", arguments={"path": "/outside/bounds"})
    assert policy.evaluate_tool_call(call3, tdef_forbidden).decision == DecisionType.FORBIDDEN
    
    # 4. requires_approval=False does NOT downgrade ASK (like process execution)
    tdef_exec = ToolDefinition(tool_id="t4", name="t", description="t", capabilities=[Capability.PROCESS_EXECUTION], requires_approval=False)
    call4 = ToolCall(call_id="4", tool_id="t4", arguments={})
    assert policy.evaluate_tool_call(call4, tdef_exec).decision == DecisionType.ASK
