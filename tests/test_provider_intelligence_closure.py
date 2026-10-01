import pytest
from src.provider_intelligence.models import (
    ProviderDefinition, ModelDefinition, TaskRequirements, Capability, 
    PrivacyLevel, ProviderType, HealthState
)
from src.provider_intelligence.provider_registry import ProviderRegistry
from src.provider_intelligence.model_registry import ModelRegistry
from src.provider_intelligence.health_manager import HealthManager
from src.provider_intelligence.quota_manager import QuotaManager
from src.provider_intelligence.candidate_selector import CandidateSelector
from src.provider_intelligence.routing_engine import RoutingEngine

@pytest.fixture
def registry_setup():
    p_reg = ProviderRegistry()
    m_reg = ModelRegistry()
    h_mgr = HealthManager()
    q_mgr = QuotaManager()
    
    # Candidate A: Vision = true
    p_reg.register_provider(ProviderDefinition(
        id="prov_a", display_name="Provider A", provider_type=ProviderType.NATIVE, endpoint_url="a", priority=50
    ))
    m_reg.register_model(ModelDefinition(
        id="model_a", provider_id="prov_a", name="model_a", display_name="Model A",
        capabilities={Capability.VISION}, is_local=False
    ))
    
    # Candidate B: Vision = false
    p_reg.register_provider(ProviderDefinition(
        id="prov_b", display_name="Provider B", provider_type=ProviderType.NATIVE, endpoint_url="b", priority=40
    ))
    m_reg.register_model(ModelDefinition(
        id="model_b", provider_id="prov_b", name="model_b", display_name="Model B",
        capabilities={Capability.TEXT_GENERATION}, is_local=False
    ))

    # Candidate C: Vision = true
    p_reg.register_provider(ProviderDefinition(
        id="prov_c", display_name="Provider C", provider_type=ProviderType.NATIVE, endpoint_url="c", priority=30
    ))
    m_reg.register_model(ModelDefinition(
        id="model_c", provider_id="prov_c", name="model_c", display_name="Model C",
        capabilities={Capability.VISION}, is_local=False
    ))
    
    # Local Candidate
    p_reg.register_provider(ProviderDefinition(
        id="local_prov", display_name="Local Prov", provider_type=ProviderType.LOCAL, endpoint_url="local", is_local=True, priority=20
    ))
    m_reg.register_model(ModelDefinition(
        id="local_model", provider_id="local_prov", name="local_model", display_name="Local Model",
        capabilities={Capability.TEXT_GENERATION}, is_local=True
    ))
    
    return p_reg, m_reg, h_mgr, q_mgr

def test_capability_preserving_fallback(registry_setup):
    p_reg, m_reg, h_mgr, q_mgr = registry_setup
    
    # Candidate A fails
    h_mgr.record_failure("prov_a", "model_a", 500)
    h_mgr.record_failure("prov_a", "model_a", 500)
    h_mgr.record_failure("prov_a", "model_a", 500)
    
    selector = CandidateSelector(p_reg, m_reg, h_mgr, q_mgr)
    engine = RoutingEngine(selector)
    
    req = TaskRequirements(hard_capabilities={Capability.VISION})
    decision = engine.select_route(req)
    
    # Must NOT select Candidate B (no vision)
    assert decision.selected_model_id != "model_b"
    # MUST select Candidate C (has vision)
    assert decision.selected_model_id == "model_c"

def test_local_only_routing(registry_setup):
    p_reg, m_reg, h_mgr, q_mgr = registry_setup
    
    selector = CandidateSelector(p_reg, m_reg, h_mgr, q_mgr)
    engine = RoutingEngine(selector)
    
    # Local only task
    req = TaskRequirements(privacy_requirement=PrivacyLevel.LOCAL_ONLY)
    decision = engine.select_route(req)
    
    # MUST select local
    assert decision.selected_model_id == "local_model"
    
    # Now make local unavailable
    h_mgr.record_failure("local_prov", "local_model", 500)
    h_mgr.record_failure("local_prov", "local_model", 500)
    h_mgr.record_failure("local_prov", "local_model", 500)
    
    decision = engine.select_route(req)
    
    # Must fail safely, must NOT route to remote
    assert decision.route_type == "FAILED"
    assert decision.selected_model_id == ""

def test_health_rate_limit(registry_setup):
    p_reg, m_reg, h_mgr, q_mgr = registry_setup
    
    # A is rate limited
    h_mgr.record_failure("prov_a", "model_a", 429)
    
    selector = CandidateSelector(p_reg, m_reg, h_mgr, q_mgr)
    engine = RoutingEngine(selector)
    
    # Both have Vision. A is rate limited (degraded/unavailable). C is healthy.
    # Note: our CandidateSelector might not explicitly drop 429, but should rank it lower or drop it.
    # In candidate_selector.py we map 429 to RateLimited and drop it if we decide to.
    # Let's ensure C is chosen. Wait, 429 in our health manager maps to RATE_LIMITED.
    # We should exclude RATE_LIMITED from candidates or score it very low.
    
    req = TaskRequirements(hard_capabilities={Capability.VISION})
    decision = engine.select_route(req)
    
    # Currently candidate_selector drops UNAVAILABLE and EXHAUSTED. 
    # To drop RATE_LIMITED we must verify.
    assert decision.selected_model_id == "model_c"

