import re
import logging

logger = logging.getLogger("aurex.audit")

def sanitize_secrets(text: str) -> str:
    if not isinstance(text, str):
        return text
    # Strip bearer tokens (using raw strings correctly)
    text = re.sub(r'(Bearer\s+)[A-Za-z0-9\-\._~+]+', r'\1[REDACTED]', text, flags=re.IGNORECASE)
    # Strip AWS keys
    text = re.sub(r'(AKIA[0-9A-Z]{16})', r'[REDACTED]', text)
    # Strip generic password fields in JSON/args
    text = re.sub(r'("?password"?\s*[:=]\s*"?)[^"&\s\}]+("?)', r'\1[REDACTED]\2', text, flags=re.IGNORECASE)
    return text

def log_audit_event(request_id: str, tool: str, operation: str, decision: str, status: str, duration: float = 0.0, **kwargs):
    sanitized_kwargs = {k: sanitize_secrets(str(v)) for k, v in kwargs.items()}
    logger.info(f"AUDIT | Req:{request_id} | Tool:{tool} | Op:{operation} | Decision:{decision} | Status:{status} | Duration:{duration:.2f}s | {sanitized_kwargs}")
