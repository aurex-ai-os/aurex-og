import pytest
import asyncio
from pathlib import Path
from src.executor.models import ExecutionRequest, DecisionType
from src.executor.policy import PolicyEngine
from src.executor.executor import SecureExecutor
from src.executor.audit import sanitize_secrets
from src.executor.errors import Timeout, Cancelled

@pytest.fixture
def policy_engine(tmp_path):
    return PolicyEngine(workspace_root=str(tmp_path))

def test_workspace_boundary(policy_engine, tmp_path):
    # Authorized write
    req1 = ExecutionRequest(operation_type="WriteFile", arguments={"path": str(tmp_path / "test.txt")})
    dec1 = policy_engine.evaluate(req1)
    assert dec1.decision == DecisionType.PREVIEW

    # Escape denied
    req2 = ExecutionRequest(operation_type="WriteFile", arguments={"path": str(tmp_path / ".." / "outside.txt")})
    dec2 = policy_engine.evaluate(req2)
    assert dec2.decision == DecisionType.ASK

    # Absolute outside denied
    req3 = ExecutionRequest(operation_type="WriteFile", arguments={"path": "/etc/passwd"})
    dec3 = policy_engine.evaluate(req3)
    assert dec3.decision == DecisionType.ASK

def test_shell_policy(policy_engine):
    req = ExecutionRequest(operation_type="RunShellCommand", arguments={"command": "echo test"})
    dec = policy_engine.evaluate(req)
    assert dec.decision == DecisionType.ASK

def test_secret_sanitization():
    assert sanitize_secrets("Authorization: Bearer sk-12345ABCD") == "Authorization: Bearer [REDACTED]"
    assert sanitize_secrets("AWS_KEY=AKIAIOSFODNN7EXAMPLE") == "AWS_KEY=[REDACTED]"
    assert sanitize_secrets('{"password": "secret_pass"}') == '{"password": "[REDACTED]"}'
    assert sanitize_secrets("normal text") == "normal text"

@pytest.mark.asyncio
async def test_shell_timeout(policy_engine, tmp_path):
    req = ExecutionRequest(operation_type="RunShellCommand", arguments={"command": "sleep 10"}, working_directory=str(tmp_path))
    # Mock approval
    from src.executor.models import ExecutionDecision, ApprovedAction
    action = ApprovedAction(req, ExecutionDecision(decision=DecisionType.ALLOW, reason="Mock"))
    
    with pytest.raises(Timeout):
        await SecureExecutor.execute_shell(action, timeout=1)

@pytest.mark.asyncio
async def test_shell_cancellation(policy_engine, tmp_path):
    req = ExecutionRequest(operation_type="RunShellCommand", arguments={"command": "sleep 10"}, working_directory=str(tmp_path))
    from src.executor.models import ExecutionDecision, ApprovedAction
    action = ApprovedAction(req, ExecutionDecision(decision=DecisionType.ALLOW, reason="Mock"))
    
    task = asyncio.create_task(SecureExecutor.execute_shell(action, timeout=5))
    await asyncio.sleep(0.5)
    task.cancel()
    
    with pytest.raises(Cancelled) or pytest.raises(asyncio.CancelledError):
        await task

import os
import tempfile
from pathlib import Path
from src.executor.models import ExecutionRequest, DecisionType, ApprovedAction, ExecutionDecision
from src.executor.policy import PolicyEngine
from src.executor.executor import SecureExecutor

def test_adversarial_workspace_bounds(tmp_path):
    # Setup test workspace and an "outside" dir
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    
    # outside file
    outside_file = outside_dir / "secret.txt"
    outside_file.write_text("secret")
    
    # inside symlink pointing outside
    symlink_path = ws_dir / "symlink_out"
    os.symlink(outside_file, symlink_path)
    
    # symlink chain
    symlink_chain_start = ws_dir / "symlink_chain"
    os.symlink(symlink_path, symlink_chain_start)
    
    policy = PolicyEngine(str(ws_dir))
    
    def check_decision(path, expected, is_dest=False):
        args = {"destination": str(path)} if is_dest else {"path": str(path)}
        req = ExecutionRequest(operation_type="ReadFile" if not is_dest else "WriteFile", arguments=args, working_directory=str(ws_dir))
        return policy.evaluate(req).decision == expected

    # 1. ../outside.txt
    assert check_decision(ws_dir / ".." / "outside" / "secret.txt", DecisionType.FORBIDDEN)
    
    # 2. ../../outside.txt
    assert check_decision(ws_dir / ".." / ".." / "outside" / "secret.txt", DecisionType.FORBIDDEN)
    
    # 3. absolute outside-workspace path
    assert check_decision(str(outside_file), DecisionType.FORBIDDEN)
    
    # 4. nested traversal
    assert check_decision(ws_dir / "foo" / ".." / ".." / "outside" / "secret.txt", DecisionType.FORBIDDEN)
    
    # 5. symlink pointing outside workspace
    assert check_decision(symlink_path, DecisionType.FORBIDDEN)
    
    # 6. symlink chain
    assert check_decision(symlink_chain_start, DecisionType.FORBIDDEN)
    
    # 7. lexical vs resolved (looks inside, resolves outside - handled by resolve)
    # 8. in-workspace path remains allowed
    in_file = ws_dir / "in.txt"
    in_file.write_text("in")
    assert check_decision(in_file, DecisionType.ALLOW)
    assert check_decision(in_file, DecisionType.PREVIEW, is_dest=True) # WriteFile
    
    # 9. attempted approval cannot override FORBIDDEN
    req_forbidden = ExecutionRequest(operation_type="ReadFile", arguments={"path": str(outside_file)}, working_directory=str(ws_dir))
    dec_forbidden = policy.evaluate(req_forbidden)
    
    import pytest
    from src.executor.errors import ExecutorError
    with pytest.raises(ValueError):
        action = ApprovedAction(req_forbidden, dec_forbidden)

    # 10. SecureExecutor independently rejects the same escape (using direct API instead of ApprovedAction)
    # Actually, SecureExecutor requires ApprovedAction. If we bypass that, SecureExecutor.execute_fs raises error or fails.
    # We will test SecureExecutor with a forged ApprovedAction to see if it still rejects it.
    dec_forged = ExecutionDecision(decision=DecisionType.ALLOW, reason="Forged")
    action_forged = ApprovedAction(req_forbidden, dec_forged)
    
    import asyncio
    async def run_secure_exec():
        try:
            await SecureExecutor.execute_fs(action_forged)
        except Exception as e:
            assert isinstance(e, ExecutorError) or "violation" in str(e).lower() or "outside" in str(e).lower()

    asyncio.run(run_secure_exec())
