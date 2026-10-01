
class ExecutorError(Exception): pass
class PolicyDenied(ExecutorError): pass
class ApprovalRequired(ExecutorError): pass
class WorkspaceViolation(ExecutorError): pass
class Timeout(ExecutorError): pass
class Cancelled(ExecutorError): pass
class ExecutionFailed(ExecutorError): pass
class InvalidRequest(ExecutorError): pass
class ResourceNotFound(ExecutorError): pass
class SecretBlocked(ExecutorError): pass
