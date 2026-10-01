"""
quota_manager.py

Tracks per-provider quota and rate limit state.
Parses standard rate-limit headers from API responses.
"""

import time
import logging
from typing import Dict, Optional
from src.provider_intelligence.models import QuotaState

logger = logging.getLogger(__name__)


class QuotaManager:
    def __init__(self):
        self._quota_state: Dict[str, QuotaState] = {}
        self._rate_limit_reset_at: Dict[str, float] = {}   # epoch seconds
        self._requests_remaining: Dict[str, int] = {}
        self._tokens_remaining: Dict[str, int] = {}

    def update_quota_from_headers(self, provider_id: str, headers: Dict[str, str]):
        """
        Parse standard rate-limit response headers and update quota state.

        Supports:
        - x-ratelimit-remaining-requests / x-ratelimit-remaining
        - x-ratelimit-remaining-tokens
        - x-ratelimit-reset-requests / x-ratelimit-reset / retry-after
        - ratelimit-remaining (OpenRouter / OmniRoute style)
        - ratelimit-reset
        """
        if not headers:
            return

        # Normalize header keys to lowercase
        h = {k.lower(): v for k, v in headers.items()}

        # Parse remaining requests
        for key in ("x-ratelimit-remaining-requests", "x-ratelimit-remaining", "ratelimit-remaining"):
            if key in h:
                try:
                    remaining = int(h[key])
                    self._requests_remaining[provider_id] = remaining
                    if remaining == 0:
                        self._quota_state[provider_id] = QuotaState.RATE_LIMITED
                        logger.warning(f"[QuotaManager] {provider_id}: request quota exhausted (header: {key})")
                    elif remaining < 5:
                        self._quota_state[provider_id] = QuotaState.LIMITED
                    else:
                        # Only upgrade to HEALTHY if we're not already EXHAUSTED
                        if self._quota_state.get(provider_id) not in (QuotaState.EXHAUSTED,):
                            self._quota_state[provider_id] = QuotaState.HEALTHY
                except (ValueError, TypeError):
                    pass
                break

        # Parse remaining tokens
        for key in ("x-ratelimit-remaining-tokens", "ratelimit-remaining-tokens"):
            if key in h:
                try:
                    tok_remaining = int(h[key])
                    self._tokens_remaining[provider_id] = tok_remaining
                    if tok_remaining == 0:
                        self._quota_state[provider_id] = QuotaState.RATE_LIMITED
                        logger.warning(f"[QuotaManager] {provider_id}: token quota exhausted (header: {key})")
                except (ValueError, TypeError):
                    pass
                break

        # Parse reset timestamp
        for key in ("x-ratelimit-reset-requests", "x-ratelimit-reset", "ratelimit-reset", "retry-after"):
            if key in h:
                try:
                    val = h[key]
                    # "retry-after" is usually seconds; reset headers can be ISO or epoch
                    if val.isdigit():
                        reset_at = time.time() + float(val)
                    else:
                        # Try parsing ISO 8601 or float epoch
                        from datetime import datetime, timezone
                        try:
                            reset_at = datetime.fromisoformat(val.replace("Z", "+00:00")).timestamp()
                        except Exception:
                            reset_at = time.time() + 60.0  # fallback: 60s
                    self._rate_limit_reset_at[provider_id] = reset_at
                except (ValueError, TypeError):
                    pass
                break

    def set_quota_exhausted(self, provider_id: str):
        """Manually mark a provider as quota-exhausted (e.g. from 402 or 429 response body)."""
        self._quota_state[provider_id] = QuotaState.EXHAUSTED
        logger.warning(f"[QuotaManager] {provider_id}: marked EXHAUSTED")

    def record_rate_limit(self, provider_id: str, retry_after_seconds: float = 60.0):
        """Called when a 429 is received. Marks the provider as RATE_LIMITED."""
        self._quota_state[provider_id] = QuotaState.RATE_LIMITED
        self._rate_limit_reset_at[provider_id] = time.time() + retry_after_seconds
        logger.warning(f"[QuotaManager] {provider_id}: RATE_LIMITED, reset in {retry_after_seconds:.0f}s")

    def get_quota_state(self, provider_id: str) -> QuotaState:
        state = self._quota_state.get(provider_id, QuotaState.HEALTHY)

        # Auto-recover RATE_LIMITED if reset window has passed
        if state == QuotaState.RATE_LIMITED:
            reset_at = self._rate_limit_reset_at.get(provider_id, 0)
            if time.time() > reset_at:
                logger.info(f"[QuotaManager] {provider_id}: rate limit window passed, promoting to LIMITED")
                self._quota_state[provider_id] = QuotaState.LIMITED
                return QuotaState.LIMITED

        return state

    def get_tokens_remaining(self, provider_id: str) -> Optional[int]:
        return self._tokens_remaining.get(provider_id)

    def get_requests_remaining(self, provider_id: str) -> Optional[int]:
        return self._requests_remaining.get(provider_id)
