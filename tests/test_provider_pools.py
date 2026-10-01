"""
tests/test_provider_pools.py  —  Phase 16
Tests for provider pool abstraction, adapters, and routing.
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.provider_intelligence.provider_pools import (
    ProviderPool, OmniRouteAdapter, FreeLLMAPIAdapter,
    QUOTA_CIRCUMVENTION_ALLOWED
)
from src.provider_intelligence.models import (
    ModelDefinition, ProviderDefinition, ProviderType, PrivacyLevel,
    TaskRequirements, HealthState, Capability
)
from src.provider_intelligence.routing_engine import RoutingEngine
from src.provider_intelligence.candidate_selector import CandidateSelector
from src.provider_intelligence.health_manager import HealthManager
from src.provider_intelligence.quota_manager import QuotaManager
from src.provider_intelligence.model_registry import ModelRegistry
from src.provider_intelligence.provider_registry import ProviderRegistry
from src.provider_intelligence.capability_registry import CapabilityRegistry


def _make_model(model_id, context_window=128000, caps=None, provider_id="openrouter"):
    caps = caps or {Capability.TEXT_GENERATION, Capability.STREAMING}
    return ModelDefinition(
        id=model_id, provider_id=provider_id,
        name=model_id, display_name=model_id,
        context_window=context_window, max_output=4096,
        capabilities=caps, is_available=True,
        health=HealthState.HEALTHY, reliability=1.0,
        metadata_source="direct", metadata_confidence=1.0
    )


def _make_provider(provider_id="openrouter", is_local=False):
    return ProviderDefinition(
        id=provider_id, display_name=provider_id,
        provider_type=ProviderType.OPENAI_COMPAT,
        endpoint_url="http://localhost", is_local=is_local,
        is_enabled=True, priority=50
    )


def _make_stack(models, providers=None):
    mr = ModelRegistry()
    pr = ProviderRegistry()
    hm = HealthManager()
    qm = QuotaManager()
    for m in models:
        mr.register_model(m)
        hm.reset(m.provider_id, m.id)
    for p in (providers or [_make_provider()]):
        pr.register_provider(p)
    sel = CandidateSelector(pr, mr, hm, qm)
    eng = RoutingEngine(sel)
    return eng, hm, qm


class TestProviderPoolAbstraction:
    def test_quota_circumvention_disabled(self):
        assert QUOTA_CIRCUMVENTION_ALLOWED is False

    def test_omniroute_adapter_info(self):
        adapter = OmniRouteAdapter(endpoint="http://localhost:8080", api_key="test")
        info = adapter.get_pool_info()
        assert info.pool_id == "omniroute"
        assert info.streaming_support is True

    def test_freellmapi_adapter_info(self):
        adapter = FreeLLMAPIAdapter(endpoint="http://localhost:8081", api_key="test")
        info = adapter.get_pool_info()
        assert info.pool_id == "freellmapi"
        assert info.privacy_characteristics == "low_trust"
        assert info.cost_characteristics == "free"

    def test_api_key_not_in_repr(self):
        adapter = OmniRouteAdapter(endpoint="http://x", api_key="super_secret_key")
        assert "super_secret_key" not in repr(adapter)
        assert "super_secret_key" not in str(adapter)

    def test_omniroute_fetch_models_returns_list(self):
        adapter = OmniRouteAdapter(endpoint="http://localhost", api_key="")
        result = adapter.fetch_models()
        assert isinstance(result, list)


class TestRoutingEngine:
    def test_normal_request_fits(self):
        m = _make_model("gpt-4o", context_window=128000)
        eng, _, _ = _make_stack([m])
        req = TaskRequirements()
        decision = eng.select_route(req, input_token_estimate=1000)
        assert decision.selected_model_id == "gpt-4o"
        assert "VERIFIED_CONTEXT_FIT" in decision.reason_codes

    def test_request_at_boundary(self):
        # 800 input + 4096 output + 200 overhead = 5096 required
        # 10000 * 0.92 = 9200 safe → fits
        m = _make_model("boundary-model", context_window=10000)
        eng, _, _ = _make_stack([m])
        req = TaskRequirements()
        decision = eng.select_route(req, input_token_estimate=800)
        assert decision.route_type != "FAILED"


    def test_request_above_boundary_eliminated(self):
        m = _make_model("tiny", context_window=100)
        eng, _, _ = _make_stack([m])
        req = TaskRequirements()
        # tiny model 100-token window can't hold 5000-token request
        decision = eng.select_route(req, input_token_estimate=5000)
        assert decision.route_type == "FAILED"
        assert "ALL_CANDIDATES_CONTEXT_INSUFFICIENT" in decision.reason_codes

    def test_selects_larger_model(self):
        small = _make_model("small", context_window=4096)
        large = _make_model("large", context_window=200000)
        eng, _, _ = _make_stack([small, large])
        req = TaskRequirements()
        decision = eng.select_route(req, input_token_estimate=50000)
        assert decision.selected_model_id == "large"

    def test_health_unhealthy_excluded(self):
        m = _make_model("sick-model", context_window=128000)
        eng, hm, _ = _make_stack([m])
        # Mark model unavailable
        for _ in range(3):
            hm.record_failure("openrouter", "sick-model", 500)
        req = TaskRequirements()
        decision = eng.select_route(req, input_token_estimate=1000)
        assert decision.route_type == "FAILED"

    def test_quota_exhausted_excluded(self):
        m = _make_model("ok-model", context_window=128000)
        eng, _, qm = _make_stack([m])
        qm.set_quota_exhausted("openrouter")
        req = TaskRequirements()
        decision = eng.select_route(req)
        assert decision.route_type == "FAILED"

    def test_reason_codes_populated(self):
        m = _make_model("gpt-4o", context_window=128000)
        eng, _, _ = _make_stack([m])
        decision = eng.select_route(TaskRequirements(), input_token_estimate=500)
        assert len(decision.reason_codes) > 0

    def test_no_candidates_returns_failed(self):
        eng, _, _ = _make_stack([])
        decision = eng.select_route(TaskRequirements())
        assert decision.route_type == "FAILED"
        assert "NO_ELIGIBLE_CANDIDATES" in decision.reason_codes

    def test_capability_registry_known_models(self):
        cr = CapabilityRegistry()
        caps = cr.get_capabilities("claude-3-5-sonnet")
        assert Capability.VISION in caps
        assert Capability.TOOL_CALLING in caps

    def test_capability_registry_unknown_model_heuristic(self):
        cr = CapabilityRegistry()
        caps = cr.get_capabilities("some-random-vision-model")
        assert Capability.VISION in caps
