"""
provider_pool_routes.py  —  Phase 14

FastAPI routes for the Provider Pools UI.
Exposes pool status, model lists, health checks, and context capacity info.
"""

from __future__ import annotations

import time
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/provider-pools", tags=["provider-pools"])


def _get_pool_registry():
    """Lazy-import to avoid circular deps at startup."""
    try:
        from src.provider_intelligence.provider_pools import (
            OmniRouteAdapter, FreeLLMAPIAdapter
        )
        from src.settings import get_setting
        pools = {}
        # OmniRoute
        omni_url = get_setting("omniroute_endpoint", "")
        omni_key = get_setting("omniroute_api_key", "")
        if omni_url:
            pools["omniroute"] = OmniRouteAdapter(endpoint=omni_url, api_key=omni_key)
        # FreeLLMAPI
        free_url = get_setting("freellmapi_endpoint", "https://api.freellm.app")
        free_key = get_setting("freellmapi_api_key", "")
        if free_url:
            pools["freellmapi"] = FreeLLMAPIAdapter(endpoint=free_url, api_key=free_key)
        return pools
    except Exception as e:
        logger.warning(f"[ProviderPoolRoutes] Could not load pool registry: {e}")
        return {}


@router.get("")
async def list_provider_pools():
    """Return status summary for all configured provider pools."""
    pools = _get_pool_registry()
    result = []
    for pool_id, adapter in pools.items():
        info = adapter.get_pool_info()
        result.append({
            "pool_id": info.pool_id,
            "display_name": info.display_name,
            "enabled": info.enabled,
            "health": info.health,
            "model_count": len(info.models),
            "streaming_support": info.streaming_support,
            "tool_calling_support": info.tool_calling_support,
            "vision_support": info.vision_support,
            "privacy_characteristics": info.privacy_characteristics,
            "cost_characteristics": info.cost_characteristics,
            "reliability_score": info.reliability_score,
            "last_failure": info.last_failure.isoformat() if info.last_failure else None,
            "last_success": info.last_successful_health_check.isoformat() if info.last_successful_health_check else None,
        })
    # Always include DIRECT pool
    result.insert(0, {
        "pool_id": "direct",
        "display_name": "Direct Providers",
        "enabled": True,
        "health": "healthy",
        "model_count": -1,  # Dynamic
        "privacy_characteristics": "standard",
        "cost_characteristics": "variable",
    })
    return {"pools": result}


@router.get("/{pool_id}/models")
async def get_pool_models(pool_id: str):
    """Return normalized model list for a specific pool."""
    if pool_id == "direct":
        return {"pool_id": "direct", "models": [], "note": "Use /api/models for direct models"}

    pools = _get_pool_registry()
    adapter = pools.get(pool_id)
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Pool '{pool_id}' not found or not configured")

    try:
        models = adapter.fetch_models()
        return {"pool_id": pool_id, "models": models, "count": len(models)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch models from {pool_id}: {e}")


@router.get("/{pool_id}/health")
async def get_pool_health(pool_id: str):
    """Return health state for a specific pool."""
    if pool_id == "direct":
        return {"pool_id": "direct", "health": "healthy"}

    pools = _get_pool_registry()
    adapter = pools.get(pool_id)
    if not adapter:
        raise HTTPException(status_code=404, detail=f"Pool '{pool_id}' not found")

    info = adapter.get_pool_info()
    return {
        "pool_id": pool_id,
        "health": info.health,
        "reliability_score": info.reliability_score,
        "last_failure": info.last_failure.isoformat() if info.last_failure else None,
    }


@router.get("/context-capacity")
async def get_context_capacity(request: Request):
    """
    Return context capacity info for the last/current model selection.
    Useful for the UI 'Context Capacity' panel.
    """
    from src.context_engine.context_admission import (
        estimate_input_tokens, calculate_required_context, safe_context_limit
    )
    # Try to pull last selection from request state or return a placeholder
    try:
        session_state = getattr(request.state, "last_routing_decision", None)
        if session_state:
            model_id = session_state.get("model_id", "unknown")
            context_window = session_state.get("context_window", 128000)
            input_tokens = session_state.get("input_tokens", 0)
            output_budget = session_state.get("output_budget", 4096)
            required = calculate_required_context(input_tokens, output_budget)
            safe = safe_context_limit(context_window)
            return {
                "model_id": model_id,
                "input_tokens": input_tokens,
                "output_budget": output_budget,
                "required": required,
                "verified_context": context_window,
                "safe_limit": safe,
                "remaining": safe - required,
                "safety_margin": safe / context_window,
                "fits": required <= safe,
            }
    except Exception:
        pass

    return {
        "note": "No active request context available",
        "input_tokens": 0,
        "output_budget": 4096,
        "required": 0,
        "verified_context": 0,
        "safe_limit": 0,
        "remaining": 0,
        "fits": True,
    }
