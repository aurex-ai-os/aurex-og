
import os
from pathlib import Path
from .models import ExecutionRequest, ExecutionDecision, DecisionType, ApprovedAction
from .registry import ToolCall, ToolDefinition, Capability
from .errors import WorkspaceViolation

class PolicyEngine:
    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root).resolve(strict=False)
        
    def _check_workspace_bounds(self, path: str, working_dir: str = None) -> tuple[bool, bool]:
        # returns (is_within_boundary, has_active_workspace)
        if not path:
            return True, False
        try:
            from src.tool_execution import get_active_workspace
            ws = get_active_workspace()
            has_ws = bool(ws) or bool(working_dir)
            
            resolved = Path(path)
            if not resolved.is_absolute():
                base = Path(working_dir) if working_dir else (Path(ws) if ws else self.workspace_root)
                resolved = (base / path).resolve(strict=False)
            else:
                resolved = resolved.resolve(strict=False)
                
            boundary = Path(ws).resolve(strict=False) if ws else self.workspace_root
            
            try:
                resolved.relative_to(boundary)
                return True, has_ws
            except ValueError:
                return False, has_ws
        except Exception:
            return False, False

    def evaluate(self, req: ExecutionRequest) -> ExecutionDecision:
        if req.working_directory:
            in_bounds, has_ws = self._check_workspace_bounds(req.working_directory, None)
            if not in_bounds:
                return ExecutionDecision(decision=DecisionType.FORBIDDEN if has_ws else DecisionType.ASK, reason="Workspace boundary violation on working directory" if has_ws else "Global system access requires approval")
        if req.operation_type in ["RunShellCommand", "RunPython", "RunExec"]:
            return ExecutionDecision(decision=DecisionType.ASK, reason="Execution requires explicit approval")
            
        if req.operation_type in ["ReadFile", "ListDirectory"]:
            target = req.arguments.get("path")
            if target:
                in_bounds, has_ws = self._check_workspace_bounds(target, req.working_directory)
                if not in_bounds:
                    return ExecutionDecision(decision=DecisionType.FORBIDDEN if has_ws else DecisionType.ASK, reason="Workspace boundary violation on read" if has_ws else "Global system read requires approval")
            return ExecutionDecision(decision=DecisionType.ALLOW, reason="Read allowed within workspace")
            
        if req.operation_type in ["WriteFile", "DeleteFile", "MoveFile", "CopyFile", "MakeDirectory"]:
            target = req.arguments.get("path")
            dest = req.arguments.get("destination")
            if target:
                in_bounds, has_ws = self._check_workspace_bounds(target, req.working_directory)
                if not in_bounds:
                    return ExecutionDecision(decision=DecisionType.FORBIDDEN if has_ws else DecisionType.ASK, reason="Workspace boundary violation on mutation target" if has_ws else "Global system mutation requires approval")
            if dest:
                in_bounds, has_ws = self._check_workspace_bounds(dest, req.working_directory)
                if not in_bounds:
                    return ExecutionDecision(decision=DecisionType.FORBIDDEN if has_ws else DecisionType.ASK, reason="Workspace boundary violation on mutation destination" if has_ws else "Global system mutation requires approval")
            return ExecutionDecision(decision=DecisionType.PREVIEW, reason="File mutation requires preview")
            
        if req.operation_type == "RunMCPTool":
            return ExecutionDecision(decision=DecisionType.ASK, reason="MCP Tool execution requires approval")
            
        return ExecutionDecision(decision=DecisionType.FORBIDDEN, reason="Unknown operation type")

    def evaluate_tool_call(self, call: ToolCall, tool_def: ToolDefinition) -> ExecutionDecision:
        caps = tool_def.capabilities
        
        # Deny inherently dangerous unaccounted states
        if Capability.CREDENTIAL_ACCESS in caps and Capability.NETWORK_ACCESS in caps:
            return ExecutionDecision(decision=DecisionType.ASK, reason="Credential exposure to network requires approval")
            
        if Capability.PROCESS_EXECUTION in caps:
            return ExecutionDecision(decision=DecisionType.ASK, reason="Process execution requires explicit approval")
            
        if Capability.MCP_EXECUTION in caps:
            return ExecutionDecision(decision=DecisionType.ASK, reason="MCP Tool execution requires explicit approval")
            
        if Capability.FILESYSTEM_WRITE in caps or Capability.FILESYSTEM_DELETE in caps:
            # Need to check bounds on the arguments if we know them
            path = call.arguments.get("path")
            dest = call.arguments.get("destination")
            if path:
                in_bounds, has_ws = self._check_workspace_bounds(path, None)
                if not in_bounds:
                    return ExecutionDecision(decision=DecisionType.FORBIDDEN if has_ws else DecisionType.ASK, reason="Workspace boundary violation" if has_ws else "Global system access requires approval")
            if dest:
                in_bounds, has_ws = self._check_workspace_bounds(dest, None)
                if not in_bounds:
                    return ExecutionDecision(decision=DecisionType.FORBIDDEN if has_ws else DecisionType.ASK, reason="Workspace boundary violation" if has_ws else "Global system access requires approval")
            return ExecutionDecision(decision=DecisionType.PREVIEW, reason="File mutation requires preview")
            
        if Capability.FILESYSTEM_READ in caps:
            path = call.arguments.get("path")
            if path:
                in_bounds, has_ws = self._check_workspace_bounds(path, None)
                if not in_bounds:
                    return ExecutionDecision(decision=DecisionType.FORBIDDEN if has_ws else DecisionType.ASK, reason="Workspace boundary violation on read" if has_ws else "Global system read requires approval")
            

        decision = DecisionType.ALLOW
        reason = "Operation allowed based on capability subset"
        
        # Default allow for safe read-only operations
        if len(caps) == 1 and caps[0] == Capability.READ_ONLY:
            decision = DecisionType.ALLOW
            reason = "Read-only tool"
            
        if tool_def.requires_approval and decision == DecisionType.ALLOW:
            decision = DecisionType.ASK
            reason = "ToolDefinition statically requires approval"
            
        return ExecutionDecision(decision=decision, reason=reason)

