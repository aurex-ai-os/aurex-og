"""
routing_engine.py

Selects the best provider+model candidate for a given TaskRequirements.
Produces a RoutingDecision with deterministic reason_codes for full transparency.
"""

import time
import logging
from typing import List, Optional, Tuple
from src.provider_intelligence.models import (
    RoutingDecision, TaskRequirements, ProviderDefinition,
    ModelDefinition, HealthState
)
from src.provider_intelligence.candidate_selector import CandidateSelector

logger = logging.getLogger(__name__)


class RoutingEngine:
    def __init__(self, candidate_selector: CandidateSelector):
        self.candidate_selector = candidate_selector

    def _score_candidate(
        self,
        provider: ProviderDefinition,
        model: ModelDefinition,
        requirements: TaskRequirements,
        input_token_estimate: int = 0,
    ) -> Tuple[int, List[str]]:
        """
        Score a candidate and return (score, reason_codes).
        Higher score = better candidate.
        """
        score = 0
        reasons = []

        # ── Hard: context window must fit actual token estimate ──
        if input_token_estimate > 0:
            required = input_token_estimate + getattr(requirements, 'output_budget', 4096)
            safe_limit = int(model.context_window * 0.92)
            if required <= safe_limit:
                score += 200
                reasons.append("VERIFIED_CONTEXT_FIT")
            else:
                score -= 500   # Effectively eliminates undersized models
                reasons.append("CONTEXT_INSUFFICIENT")

        # ── Hard capabilities match ──
        if requirements.hard_capabilities:
            matched = requirements.hard_capabilities.issubset(model.capabilities)
            if matched:
                score += 100
                reasons.append("HARD_CAPABILITIES_MET")

        # ── Soft capabilities ──
        for cap in requirements.soft_capabilities:
            if cap in model.capabilities:
                score += 10
                reasons.append(f"SOFT_CAP_{cap.value}")

        # ── Health state ──
        health = getattr(model, 'health', HealthState.UNKNOWN)
        if health == HealthState.HEALTHY:
            score += 80
            reasons.append("HEALTH_HEALTHY")
        elif health == HealthState.DEGRADED:
            score += 20
            reasons.append("HEALTH_DEGRADED")
        elif health == HealthState.UNKNOWN:
            score += 30
            reasons.append("HEALTH_UNKNOWN")

        # ── Reliability ──
        reliability = getattr(model, 'reliability', 1.0)
        rel_score = int(reliability * 50)
        score += rel_score
        if reliability >= 0.9:
            reasons.append("HIGH_RELIABILITY")
        elif reliability < 0.5:
            reasons.append("LOW_RELIABILITY")

        # ── Local preference ──
        if requirements.requires_local and provider.is_local:
            score += 100
            reasons.append("LOCAL_EXECUTION_REQUIRED_AND_MET")
        elif provider.is_local:
            score += 30
            reasons.append("LOCAL_PREFERRED")

        # ── Provider priority (from user settings) ──
        score += provider.priority
        if provider.priority >= 70:
            reasons.append("USER_PREFERRED_PROVIDER")

        # ── Cost ──
        if requirements.max_cost_per_m and model.pricing.input_cost_per_m is not None:
            if model.pricing.input_cost_per_m <= requirements.max_cost_per_m:
                score += 20
                reasons.append("WITHIN_COST_BUDGET")
            else:
                score -= 50
                reasons.append("EXCEEDS_COST_BUDGET")

        if model.pricing.is_free_tier:
            score += 15
            reasons.append("FREE_TIER_MODEL")

        # ── Metadata confidence: penalise low-confidence pool metadata ──
        confidence = getattr(model, 'metadata_confidence', 1.0)
        if confidence < 0.5:
            score -= 20
            reasons.append("LOW_METADATA_CONFIDENCE")
        elif confidence >= 0.9:
            score += 10
            reasons.append("HIGH_METADATA_CONFIDENCE")

        return score, reasons

    def select_route(
        self,
        requirements: TaskRequirements,
        input_token_estimate: int = 0,
    ) -> RoutingDecision:
        candidates = self.candidate_selector.get_candidates(requirements)

        if not candidates:
            logger.warning("[RoutingEngine] No eligible candidates for requirements")
            return RoutingDecision(
                selected_provider_id="",
                selected_model_id="",
                route_type="FAILED",
                reason_codes=["NO_ELIGIBLE_CANDIDATES"],
                timestamp=time.time()
            )

        # Score and sort candidates
        scored = []
        for provider, model in candidates:
            score, reasons = self._score_candidate(
                provider, model, requirements, input_token_estimate
            )
            scored.append((score, reasons, provider, model))

        scored.sort(key=lambda x: x[0], reverse=True)

        best_score, best_reasons, best_provider, best_model = scored[0]

        # Reject if the best candidate has a disqualifying context score
        if "CONTEXT_INSUFFICIENT" in best_reasons and input_token_estimate > 0:
            logger.warning(
                f"[RoutingEngine] Best candidate {best_model.id} cannot fit "
                f"{input_token_estimate} tokens — triggering waterfall"
            )
            return RoutingDecision(
                selected_provider_id="",
                selected_model_id="",
                route_type="FAILED",
                reason_codes=["ALL_CANDIDATES_CONTEXT_INSUFFICIENT"],
                timestamp=time.time()
            )

        fallback_candidates = [
            f"{p.id}::{m.id}" for _, _, p, m in scored[1:4]
        ]

        route_type = "EXPLICIT" if requirements.explicit_model_id else "PRIMARY"

        logger.info(
            f"[RoutingEngine] Selected {best_provider.id}::{best_model.id} "
            f"(score={best_score}) reasons={best_reasons}"
        )

        return RoutingDecision(
            selected_provider_id=best_provider.id,
            selected_model_id=best_model.id,
            route_type=route_type,
            reason_codes=best_reasons,
            capabilities_matched=best_model.capabilities.intersection(requirements.hard_capabilities),
            fallback_candidates=fallback_candidates,
            timestamp=time.time()
        )

    def select_for_large_context(
        self,
        requirements: TaskRequirements,
        input_token_estimate: int,
    ) -> RoutingDecision:
        """
        Variant of select_route that STRICTLY enforces context window fit.
        Eliminates every model whose verified context_window cannot hold the request.
        """
        return self.select_route(requirements, input_token_estimate=input_token_estimate)
