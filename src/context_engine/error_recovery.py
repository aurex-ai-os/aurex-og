"""
error_recovery.py  —  Phase 11

Classifies upstream provider failures and drives structured recovery.
Prevents retry storms. Never retries the exact same payload twice for CONTEXT_OVERFLOW.
"""

from __future__ import annotations

import asyncio
import logging
from enum import Enum
from typing import Optional, Callable, Any

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BASE_BACKOFF = 1.5   # seconds


class ErrorClass(str, Enum):
    CONTEXT_OVERFLOW    = "CONTEXT_OVERFLOW"
    RATE_LIMIT          = "RATE_LIMIT"
    AUTH_FAILURE        = "AUTH_FAILURE"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    TIMEOUT             = "TIMEOUT"
    NETWORK_ERROR       = "NETWORK_ERROR"
    INVALID_REQUEST     = "INVALID_REQUEST"
    MODEL_UNAVAILABLE   = "MODEL_UNAVAILABLE"
    TOOL_PROTOCOL_ERROR = "TOOL_PROTOCOL_ERROR"
    UNKNOWN             = "UNKNOWN"


# ── Context overflow message patterns ────────────────────────────────────────
_OVERFLOW_PATTERNS = [
    "context length exceeded",
    "prompt too large",
    "maximum input tokens",
    "request too large",
    "context window",
    "tokens in your prompt",
    "exceeds max",
    "input is too long",
    "maximum context length",
]


class ErrorClassifier:
    @staticmethod
    def classify(error: Exception, status_code: int = 0) -> ErrorClass:
        msg = str(error).lower()

        if status_code == 401 or status_code == 403:
            return ErrorClass.AUTH_FAILURE

        if status_code == 429:
            return ErrorClass.RATE_LIMIT

        if status_code == 400:
            for pattern in _OVERFLOW_PATTERNS:
                if pattern in msg:
                    return ErrorClass.CONTEXT_OVERFLOW
            return ErrorClass.INVALID_REQUEST

        if status_code == 413:
            return ErrorClass.CONTEXT_OVERFLOW

        if status_code in (402, 502, 503, 504):
            return ErrorClass.PROVIDER_UNAVAILABLE

        if status_code == 404:
            return ErrorClass.MODEL_UNAVAILABLE

        # Network / timeout
        if any(t in msg for t in ("timeout", "timed out", "read timeout")):
            return ErrorClass.TIMEOUT
        if any(t in msg for t in ("connection", "network", "unreachable", "eof", "reset")):
            return ErrorClass.NETWORK_ERROR

        # Context overflow by message content (e.g. no HTTP status)
        for pattern in _OVERFLOW_PATTERNS:
            if pattern in msg:
                return ErrorClass.CONTEXT_OVERFLOW

        if "tool" in msg or "function" in msg:
            return ErrorClass.TOOL_PROTOCOL_ERROR

        return ErrorClass.UNKNOWN


class RecoveryEngine:
    """
    Drives structured retry/recovery for classified errors.
    Prevents retry storms: max MAX_RETRIES retries, exponential backoff,
    never sends the same payload twice for CONTEXT_OVERFLOW.
    """

    def __init__(self, classifier: Optional[ErrorClassifier] = None):
        self.classifier = classifier or ErrorClassifier()

    async def recover(
        self,
        call_fn: Callable[[], Any],
        error: Exception,
        status_code: int = 0,
        context_reducer: Optional[Callable[[], Any]] = None,
        fallback_fn: Optional[Callable[[], Any]] = None,
    ) -> Any:
        """
        Attempt structured recovery.

        - call_fn: the original call (may be retried with reduced context)
        - error: the exception that triggered recovery
        - status_code: HTTP status if available
        - context_reducer: callable that returns a new (reduced) call_fn for CONTEXT_OVERFLOW
        - fallback_fn: called when all retries exhausted
        """
        error_class = self.classifier.classify(error, status_code)
        logger.warning(f"[RecoveryEngine] Error class={error_class.value} status={status_code}: {error}")

        if error_class == ErrorClass.AUTH_FAILURE:
            logger.error("[RecoveryEngine] Auth failure — not retrying")
            raise error

        if error_class == ErrorClass.CONTEXT_OVERFLOW:
            if context_reducer is None:
                logger.error("[RecoveryEngine] Context overflow but no reducer provided")
                raise error
            # Use the structurally different (reduced) call — never same payload
            logger.info("[RecoveryEngine] Context overflow → using context_reducer")
        # Context reducer: the result is already a coroutine from context_reducer()
        # Wrap it into a callable for _retry_with_backoff
        import inspect
        reduced = context_reducer()
        if inspect.iscoroutine(reduced):
            # Already a coroutine — await directly
            try:
                return await reduced
            except Exception as e:
                raise e
        # Otherwise treat as callable
        return await self._retry_with_backoff(reduced, max_retries=1)


        if error_class == ErrorClass.RATE_LIMIT:
            return await self._retry_with_backoff(call_fn, max_retries=MAX_RETRIES, base=5.0)

        if error_class in (ErrorClass.PROVIDER_UNAVAILABLE, ErrorClass.NETWORK_ERROR, ErrorClass.TIMEOUT):
            if fallback_fn:
                logger.info(f"[RecoveryEngine] {error_class.value} → trying fallback provider")
                return await self._retry_with_backoff(fallback_fn, max_retries=1)
            return await self._retry_with_backoff(call_fn, max_retries=2)

        if error_class == ErrorClass.INVALID_REQUEST:
            logger.error("[RecoveryEngine] Invalid request — not retrying")
            raise error

        # UNKNOWN / TOOL_PROTOCOL_ERROR: one cautious retry
        return await self._retry_with_backoff(call_fn, max_retries=1)

    async def _retry_with_backoff(
        self,
        call_fn: Callable[[], Any],
        max_retries: int = MAX_RETRIES,
        base: float = BASE_BACKOFF,
    ) -> Any:
        last_error = None
        for attempt in range(max_retries):
            wait = base * (2 ** attempt)
            if attempt > 0:
                logger.info(f"[RecoveryEngine] Retry {attempt}/{max_retries} after {wait:.1f}s")
                await asyncio.sleep(wait)
            try:
                result = call_fn()
                if asyncio.iscoroutine(result):
                    return await result
                return result
            except Exception as e:
                last_error = e
                logger.warning(f"[RecoveryEngine] Attempt {attempt+1} failed: {e}")
        logger.error(f"[RecoveryEngine] All {max_retries} retries exhausted")
        raise last_error
