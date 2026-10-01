import shutil
import os
import asyncio
import subprocess
import time
from .models import ApprovedAction, ExecutionRequest
from .errors import ExecutionFailed, Timeout, Cancelled, PolicyDenied, ExecutorError
from .audit import log_audit_event, sanitize_secrets

class SecureExecutor:

    @staticmethod
    def _sanitize_env(env: dict) -> dict:
        if not env:
            return {}
        safe_env = {}
        # Block known secret patterns in env keys
        blocked_substrings = ["API_KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "AUTH"]
        for k, v in env.items():
            k_upper = k.upper()
            if any(sub in k_upper for sub in blocked_substrings):
                continue
            safe_env[k] = v
        return safe_env

    @staticmethod
    async def execute_shell(action: ApprovedAction, timeout: int = 60) -> dict:
        req = action.request
        cmd = req.arguments.get("command", "")
        cwd = req.working_directory
        
        start_time = time.time()
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                status = "SUCCESS" if proc.returncode == 0 else "FAILED"
                log_audit_event(req.task_id or "N/A", req.origin_tool, req.operation_type, "ALLOW", status, time.time() - start_time)
                return {
                    "stdout": sanitize_secrets(stdout.decode(errors='replace'))[:10000],
                    "stderr": sanitize_secrets(stderr.decode(errors='replace'))[:10000],
                    "returncode": proc.returncode
                }
            except (asyncio.TimeoutError, TimeoutError):
                proc.terminate()
                await proc.wait()
                log_audit_event(req.task_id or "N/A", req.origin_tool, req.operation_type, "ALLOW", "TIMEOUT", time.time() - start_time)
                raise Timeout(f"Execution timed out after {timeout} seconds")
        except ExecutorError:
            raise
        except asyncio.CancelledError:
            log_audit_event(req.task_id or "N/A", req.origin_tool, req.operation_type, "ALLOW", "CANCELLED", time.time() - start_time)
            raise Cancelled("Execution was cancelled")
        except Exception as e:
            log_audit_event(req.task_id or "N/A", req.origin_tool, req.operation_type, "ALLOW", "ERROR", time.time() - start_time, error=str(e))
            raise ExecutionFailed(f"Failed to execute: {str(e)}")

    @staticmethod
    async def execute_exec(action: ApprovedAction, *args: str, timeout: int = 60, env=None) -> dict:
        req = action.request
        cwd = req.working_directory
        start_time = time.time()
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=cwd,
                env=SecureExecutor._sanitize_env(env),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                status = "SUCCESS" if proc.returncode == 0 else "FAILED"
                log_audit_event(req.task_id or "N/A", req.origin_tool, req.operation_type, "ALLOW", status, time.time() - start_time)
                return {
                    "stdout": sanitize_secrets(stdout.decode(errors='replace'))[:10000],
                    "stderr": sanitize_secrets(stderr.decode(errors='replace'))[:10000],
                    "returncode": proc.returncode
                }
            except (asyncio.TimeoutError, TimeoutError):
                proc.terminate()
                await proc.wait()
                log_audit_event(req.task_id or "N/A", req.origin_tool, req.operation_type, "ALLOW", "TIMEOUT", time.time() - start_time)
                raise Timeout(f"Execution timed out after {timeout} seconds")
        except ExecutorError:
            raise
        except asyncio.CancelledError:
            log_audit_event(req.task_id or "N/A", req.origin_tool, req.operation_type, "ALLOW", "CANCELLED", time.time() - start_time)
            raise Cancelled("Execution was cancelled")
        except Exception as e:
            log_audit_event(req.task_id or "N/A", req.origin_tool, req.operation_type, "ALLOW", "ERROR", time.time() - start_time, error=str(e))
            raise ExecutionFailed(f"Failed to execute: {str(e)}")

    @staticmethod
    async def execute_fs(action: ApprovedAction) -> dict:
        req = action.request
        op = req.operation_type
        args = req.arguments
        
        try:
            if op == "WriteFile":
                path = args.get("path")
                content = args.get("content", "")
                mode = args.get("mode", "w")
                with open(path, mode) as f:
                    f.write(content)
                return {"status": "SUCCESS"}
            elif op == "DeleteFile":
                path = args.get("path")
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                return {"status": "SUCCESS"}
            elif op == "MoveFile" or op == "CopyFile":
                src = args.get("path")
                dst = args.get("destination")
                if op == "MoveFile":
                    shutil.move(src, dst)
                else:
                    if os.path.isdir(src):
                        shutil.copytree(src, dst)
                    else:
                        shutil.copy2(src, dst)
                return {"status": "SUCCESS"}
            elif op == "MakeDirectory":
                path = args.get("path")
                os.makedirs(path, exist_ok=True)
                return {"status": "SUCCESS"}
            else:
                raise ExecutionFailed(f"Unsupported FS operation: {op}")
        except Exception as e:
            # Do not leak absolute paths that might contain user names in generic exceptions if we can avoid it, 
            # but we already sanitize secrets.
            err_msg = sanitize_secrets(str(e))
            log_audit_event(req.task_id or "N/A", req.origin_tool, req.operation_type, "ALLOW", "ERROR", error=err_msg)
            raise ExecutionFailed(f"FS operation failed: {err_msg}")
