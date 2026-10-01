import pytest
from src.provider_intelligence.models import (
    ProviderDefinition, ModelDefinition, TaskRequirements, Capability, 
    PrivacyLevel, ProviderType
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
    
    # Provider A - OpenAI
    p_reg.register_provider(ProviderDefinition(
        id="openai", display_name="OpenAI", provider_type=ProviderType.NATIVE, endpoint_url="api.openai.com", is_local=False, priority=50
    ))
    m_reg.register_model(ModelDefinition(
        id="gpt-4o", provider_id="openai", name="gpt-4o", display_name="GPT-4o",
        capabilities={Capability.TEXT_GENERATION, Capability.VISION, Capability.TOOL_CALLING},
        is_local=False
    ))
    m_reg.register_model(ModelDefinition(
        id="gpt-3.5", provider_id="openai", name="gpt-3.5", display_name="GPT-3.5",
        capabilities={Capability.TEXT_GENERATION},
        is_local=False
    ))
    
    # Provider B - Local Ollama
    p_reg.register_provider(ProviderDefinition(
        id="ollama", display_name="Ollama", provider_type=ProviderType.LOCAL, endpoint_url="localhost:11434", is_local=True, priority=80
    ))
    m_reg.register_model(ModelDefinition(
        id="llama3", provider_id="ollama", name="llama3", display_name="Llama 3",
        capabilities={Capability.TEXT_GENERATION, Capability.LOCAL_EXECUTION},
        is_local=True
    ))
    
    h_mgr = HealthManager()
    q_mgr = QuotaManager()
    
    return p_reg, m_reg, h_mgr, q_mgr

def test_routing_vision_requirement(registry_setup):
    p_reg, m_reg, h_mgr, q_mgr = registry_setup
    selector = CandidateSelector(p_reg, m_reg, h_mgr, q_mgr)
    engine = RoutingEngine(selector)
    
    req = TaskRequirements(hard_capabilities={Capability.VISION})
    decision = engine.select_route(req)
    
    assert decision.selected_provider_id == "openai"
    assert decision.selected_model_id == "gpt-4o"
    
def test_routing_local_privacy(registry_setup):
    p_reg, m_reg, h_mgr, q_mgr = registry_setup
    selector = CandidateSelector(p_reg, m_reg, h_mgr, q_mgr)
    engine = RoutingEngine(selector)
    
    req = TaskRequirements(privacy_requirement=PrivacyLevel.LOCAL_ONLY)
    decision = engine.select_route(req)
    
    assert decision.selected_provider_id == "ollama"
    assert decision.selected_model_id == "llama3"
    
def test_routing_provider_disabled(registry_setup):
    p_reg, m_reg, h_mgr, q_mgr = registry_setup
    p_reg.get_provider("openai").is_enabled = False
    
    selector = CandidateSelector(p_reg, m_reg, h_mgr, q_mgr)
    engine = RoutingEngine(selector)
    
    req = TaskRequirements(hard_capabilities={Capability.VISION})
    decision = engine.select_route(req)
    
    # OpenAI is disabled, no other model has vision
    assert decision.route_type == "FAILED"
    assert decision.selected_provider_id == ""

def test_routing_health_failure(registry_setup):
    p_reg, m_reg, h_mgr, q_mgr = registry_setup
    # Simulate failures on OpenAI
    h_mgr.record_failure("openai", "gpt-4o", 500)
    h_mgr.record_failure("openai", "gpt-4o", 500)
    h_mgr.record_failure("openai", "gpt-4o", 500)
    
    selector = CandidateSelector(p_reg, m_reg, h_mgr, q_mgr)
    engine = RoutingEngine(selector)
    
    req = TaskRequirements(hard_capabilities={Capability.VISION})
    decision = engine.select_route(req)
    
    # Exceeded threshold, should fail
    assert decision.route_type == "FAILED"
