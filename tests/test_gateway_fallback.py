"""
tests/test_gateway_fallback.py  —  Phase 16
Tests for fallback, recovery, quota, health, retry storm prevention.
"""
import pytest, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.provider_intelligence.health_manager import HealthManager
from src.provider_intelligence.quota_manager import QuotaManager
from src.provider_intelligence.models import HealthState, QuotaState
from src.context_engine.error_recovery import ErrorClassifier, ErrorClass


class TestGatewayFallback:
    def test_rate_limit_marks_rate_limited(self):
        hm = HealthManager()
        hm.record_failure("openrouter", "gpt-4o", 429)
        assert hm.get_health("openrouter", "gpt-4o") == HealthState.RATE_LIMITED

    def test_three_failures_marks_unavailable(self):
        hm = HealthManager()
        for _ in range(3):
            hm.record_failure("freellmapi", "model-x", 500)
        assert hm.get_health("freellmapi", "model-x") == HealthState.UNAVAILABLE

    def test_success_after_failure_restores_healthy(self):
        hm = HealthManager()
        hm.record_failure("prov", "m", 500)
        hm.record_success("prov", "m")
        assert hm.get_health("prov", "m") == HealthState.HEALTHY

    def test_quota_header_parses_zero(self):
        qm = QuotaManager()
        qm.update_quota_from_headers("openai", {"x-ratelimit-remaining-requests": "0"})
        # remaining=0 via header → RATE_LIMITED or LIMITED depending on implementation
        state = qm.get_quota_state("openai")
        assert state in (QuotaState.RATE_LIMITED, QuotaState.LIMITED)

    def test_quota_auto_recovers_after_reset(self):
        import time
        qm = QuotaManager()
        qm.record_rate_limit("openai", retry_after_seconds=0.01)
        time.sleep(0.05)
        state = qm.get_quota_state("openai")
        assert state == QuotaState.LIMITED  # promoted after reset window

    def test_retry_storm_prevention_max_retries(self):
        """Ensure RecoveryEngine only retries MAX_RETRIES times."""
        from src.context_engine.error_recovery import RecoveryEngine
        import asyncio
        engine = RecoveryEngine()
        call_count = [0]

        async def flaky_call():
            call_count[0] += 1
            raise Exception("network error")

        async def run():
            with pytest.raises(Exception):
                await engine.recover(
                    call_fn=flaky_call,
                    error=Exception("network error"),
                    status_code=503,
                )

        asyncio.run(run())
        assert call_count[0] <= 3

    def test_context_overflow_does_not_retry_same_payload(self):
        """CONTEXT_OVERFLOW must call context_reducer, not the original call."""
        from src.context_engine.error_recovery import RecoveryEngine
        import asyncio
        engine = RecoveryEngine()
        original_calls = [0]
        reduced_calls = [0]

        def original():
            original_calls[0] += 1
            raise Exception("context length exceeded")

        async def _reduced_impl():
            reduced_calls[0] += 1
            return "ok_reduced"

        # context_reducer must be a callable that returns a coroutine
        def reduced():
            return _reduced_impl()

        async def run():
            return await engine.recover(
                call_fn=original,
                error=Exception("context length exceeded"),
                status_code=400,
                context_reducer=reduced,
            )

        result = asyncio.run(run())
        assert result == "ok_reduced"
        assert original_calls[0] == 0    # original NOT retried
        assert reduced_calls[0] == 1     # reducer called once


    def test_auth_failure_not_retried(self):
        from src.context_engine.error_recovery import RecoveryEngine
        import asyncio
        engine = RecoveryEngine()
        call_count = [0]

        def call():
            call_count[0] += 1
            raise Exception("unauthorized")

        async def run():
            with pytest.raises(Exception):
                await engine.recover(call_fn=call, error=Exception("unauthorized"), status_code=401)

        asyncio.run(run())
        assert call_count[0] == 0  # never called (raised immediately)
