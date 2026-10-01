import pytest
import os
import shutil
from pathlib import Path
from src.executor.models import ExecutionRequest, DecisionType, ExecutionDecision, ApprovedAction
from src.executor.policy import PolicyEngine
from src.executor.executor import SecureExecutor

def test_approved_action_integrity():
    req = ExecutionRequest(operation_type="RunShellCommand", arguments={"command": "ls"})
    
    # Cannot forge FORBIDDEN
    dec_forbidden = ExecutionDecision(decision=DecisionType.FORBIDDEN, reason="Blocked")
    with pytest.raises(ValueError):
        ApprovedAction(req, dec_forbidden)
        
    # Cannot forge ASK
    dec_ask = ExecutionDecision(decision=DecisionType.ASK, reason="Needs approval")
    with pytest.raises(ValueError):
        ApprovedAction(req, dec_ask)
        
    # Mutation protection
    dec_allow = ExecutionDecision(decision=DecisionType.ALLOW, reason="Allowed")
    action = ApprovedAction(req, dec_allow)
    
    # Check that modifying the returned request doesn't affect the internal one
    exposed_req = action.request
    exposed_req.operation_type = "Hacked"
    assert action.request.operation_type == "RunShellCommand"

def test_symlink_escape(tmp_path):
    # Setup workspace
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    policy = PolicyEngine(str(workspace))
    
    # Setup outside file and a symlink to it
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")
    
    symlink = workspace / "link.txt"
    os.symlink(str(outside), str(symlink))
    
    req = ExecutionRequest(operation_type="ReadFile", arguments={"path": str(symlink)})
    dec = policy.evaluate(req)
    assert dec.decision == DecisionType.FORBIDDEN

def test_env_filtering():
    malicious_env = {
        "OPENAI_API_KEY": "sk-1234",
        "PATH": "/usr/bin",
        "SECRET_TOKEN": "abc"
    }
    safe_env = SecureExecutor._sanitize_env(malicious_env)
    assert "OPENAI_API_KEY" not in safe_env
    assert "SECRET_TOKEN" not in safe_env
    assert "PATH" in safe_env

@pytest.mark.asyncio
async def test_fail_closed_filesystem(tmp_path):
    req = ExecutionRequest(operation_type="DeleteFile", arguments={"path": str(tmp_path / "missing.txt")})
    # Mock approval to test executor fail-closed on missing file
    action = ApprovedAction(req, ExecutionDecision(decision=DecisionType.PREVIEW, reason="Mock"))
    
    from src.executor.errors import ExecutionFailed
    with pytest.raises(ExecutionFailed):
        await SecureExecutor.execute_fs(action)
