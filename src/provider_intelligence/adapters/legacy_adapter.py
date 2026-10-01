import logging
from typing import Dict, List, Tuple, Optional
from src.provider_intelligence.provider_registry import ProviderRegistry
from src.provider_intelligence.model_registry import ModelRegistry
from src.provider_intelligence.models import ProviderDefinition, ModelDefinition, ProviderType, Capability, PricingInfo
from src.chat_helpers import is_vision_model

logger = logging.getLogger(__name__)

def detect_model_capabilities(model_name: str) -> set:
    """Detect fine-grained capabilities of a model based on name and known architectures."""
    caps = {Capability.TEXT_GENERATION}
    if is_vision_model(model_name):
        caps.add(Capability.VISION)
    
    m_lc = (model_name or "").lower()
    # Explicit exclusions: models known not to support standard function/tool calling
    no_tools = any(kw in m_lc for kw in ("deepseek-r1", "gpt-oss", "note-preview", "embed", "rerank"))
    has_tools = not no_tools and any(kw in m_lc for kw in (
        "gpt-4", "gpt-5", "gpt-o", "claude", "gemini", "gemma",
        "qwen3", "qwen2.5", "mixtral", "mistral", "llama-3.1", "llama-3.2",
        "llama-3.3", "llama-4", "llama3.1", "llama3.2", "llama3.3", "llama4",
        "minimax", "kimi", "yi-", "phi-3", "phi-4", "command-r",
        "glm-4", "internlm", "hermes", "deepseek-v", "deepseek-chat",
        "nemotron-3", "nemotron-mini",
    ))
    if has_tools:
        caps.add(Capability.TOOL_CALLING)
    return caps


def sync_legacy_to_registry(
    provider_registry: ProviderRegistry, 
    model_registry: ModelRegistry,
    legacy_models: Dict[str, List[Dict]], 
    primary_url: str, 
    primary_model: str, 
    fallback_entries: List[tuple],
    owner: Optional[str] = None,
    primary_headers: Optional[Dict] = None,
):
    """
    Synchronizes Aurex's connected endpoints and models into ProviderIntelligence,
    enabling intelligent auto-switching to free, high-capability models when needed.
    """
    # 1. Register the primary session endpoint as a provider if not present
    is_primary_local = "localhost" in primary_url or "127.0.0.1" in primary_url
    if "primary" not in [p.id for p in provider_registry.get_all_providers()]:
        provider_registry.register_provider(ProviderDefinition(
            id="primary",
            display_name="Primary Provider",
            provider_type=ProviderType.LOCAL if is_primary_local else ProviderType.OPENAI_COMPAT,
            endpoint_url=primary_url,
            is_local=is_primary_local,
            priority=150,  # Highest priority for user-chosen model
            metadata={"headers": primary_headers or {}},
        ))
        
        # Register the primary model with accurate capabilities
        model_registry.register_model(ModelDefinition(
            id=primary_model,
            provider_id="primary",
            name=primary_model,
            display_name=primary_model,
            is_local=is_primary_local,
            capabilities=detect_model_capabilities(primary_model),
            pricing=PricingInfo(is_free_tier=":free" in primary_model or is_primary_local)
        ))
        
    # 2. Register legacy fallbacks
    for idx, fallback in enumerate(fallback_entries):
        f_url, f_model, f_hdrs = fallback
        p_id = f"fallback_{idx}"
        is_local = "localhost" in f_url or "127.0.0.1" in f_url
        
        provider_registry.register_provider(ProviderDefinition(
            id=p_id,
            display_name=f"Fallback {idx}",
            provider_type=ProviderType.LOCAL if is_local else ProviderType.OPENAI_COMPAT,
            endpoint_url=f_url,
            is_local=is_local,
            priority=80 - idx,
            metadata={"headers": f_hdrs or {}}
        ))
        
        m_id = f"{p_id}::{f_model}" if f_model == primary_model else f_model
        model_registry.register_model(ModelDefinition(
            id=m_id,
            provider_id=p_id,
            name=f_model,
            display_name=f_model,
            is_local=is_local,
            capabilities=detect_model_capabilities(f_model),
            pricing=PricingInfo(is_free_tier=":free" in f_model or is_local)
        ))

    # 3. Discover all enabled ModelEndpoints from database to offer automatic capability switching
    try:
        from core.database import SessionLocal, ModelEndpoint
        from src.endpoint_resolver import _endpoint_enabled_models, normalize_base, build_headers, build_chat_url
        
        db = SessionLocal()
        try:
            query = db.query(ModelEndpoint).filter(ModelEndpoint.is_enabled == True)
            if owner:
                query = query.filter((ModelEndpoint.owner == owner) | (ModelEndpoint.owner.is_(None)))
            endpoints = query.all()
            for ep in endpoints:
                ep_base = normalize_base(ep.base_url or "")
                if not ep_base:
                    continue
                p_id = f"ep_{ep.id}"
                if p_id in [p.id for p in provider_registry.get_all_providers()]:
                    continue
                is_local = "localhost" in ep_base or "127.0.0.1" in ep_base
                is_proxy_free = "bluesminds" in ep_base.lower() or "free" in (ep.name or "").lower()
                ep_headers = build_headers(ep.api_key, ep.base_url) if ep.api_key else {}
                
                provider_registry.register_provider(ProviderDefinition(
                    id=p_id,
                    display_name=ep.name or p_id,
                    provider_type=ProviderType.LOCAL if is_local else ProviderType.OPENAI_COMPAT,
                    endpoint_url=build_chat_url(ep_base),
                    is_local=is_local,
                    priority=85 if is_proxy_free or is_local else 70,
                    metadata={"headers": ep_headers, "raw_base": ep_base}
                ))
                
                for m in _endpoint_enabled_models(ep):
                    if not m or not isinstance(m, str) or m == primary_model:
                        continue
                    m_caps = detect_model_capabilities(m)
                    is_free = ":free" in m or is_proxy_free or is_local
                    
                    # Context window estimation
                    m_lc = m.lower()
                    ctx_win = 128000
                    if "gemini" in m_lc:
                        ctx_win = 1000000
                    elif "400k" in m_lc or "gpt-5.5" in m_lc:
                        ctx_win = 400000
                    elif "8k" in m_lc:
                        ctx_win = 8192

                    # Quality weighting: flagship/proven models get higher reliability
                    rel = 0.9
                    if any(top in m_lc for top in ("llama-3.3-70b", "gpt-5.5", "qwen3.8-27b", "nemotron-3-ultra")):
                        rel = 1.0
                    elif any(mid in m_lc for mid in ("70b", "32b", "120b")):
                        rel = 0.95
                    elif any(weak in m_lc for weak in ("preview", "mini", "nano", "experimental")):
                        rel = 0.75
                    
                    model_registry.register_model(ModelDefinition(
                        id=m,
                        provider_id=p_id,
                        name=m,
                        display_name=m,
                        context_window=ctx_win,
                        capabilities=m_caps,
                        is_local=is_local,
                        reliability=rel,
                        pricing=PricingInfo(is_free_tier=is_free)
                    ))
        finally:
            db.close()
    except Exception as e:
        logger.debug(f"sync_legacy_to_registry endpoint auto-discovery skipped: {e}")
