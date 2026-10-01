from typing import List, Tuple
from src.provider_intelligence.models import ModelDefinition, ProviderDefinition, TaskRequirements
from src.provider_intelligence.provider_registry import ProviderRegistry
from src.provider_intelligence.model_registry import ModelRegistry
from src.provider_intelligence.privacy_manager import PrivacyManager
from src.provider_intelligence.health_manager import HealthManager, HealthState
from src.provider_intelligence.quota_manager import QuotaManager, QuotaState

class CandidateSelector:
    def __init__(
        self,
        provider_registry: ProviderRegistry,
        model_registry: ModelRegistry,
        health_manager: HealthManager,
        quota_manager: QuotaManager
    ):
        self.provider_registry = provider_registry
        self.model_registry = model_registry
        self.health_manager = health_manager
        self.quota_manager = quota_manager
        self.privacy_manager = PrivacyManager()

    def get_candidates(
        self,
        requirements: TaskRequirements,
        input_token_estimate: int = 0,
        output_budget: int = 4096,
        context_safety_margin: float = 0.92,
    ) -> List[Tuple[ProviderDefinition, ModelDefinition]]:
        candidates = []

        all_models = self.model_registry.get_all_models()

        for model in all_models:
            if not model.is_available:
                continue

            provider = self.provider_registry.get_provider(model.provider_id)
            if not provider or not provider.is_enabled:
                continue

            # Hard filters
            if requirements.explicit_provider_id and provider.id != requirements.explicit_provider_id:
                continue
            if requirements.explicit_model_id and model.id != requirements.explicit_model_id:
                continue

            # Privacy checks
            if not self.privacy_manager.is_provider_allowed(requirements, provider, model):
                continue

            # Capability checks
            if requirements.hard_capabilities and not requirements.hard_capabilities.issubset(model.capabilities):
                continue

            # Context window: hard-eliminate models that cannot fit actual token estimate
            safe_context = int(model.context_window * context_safety_margin)
            if input_token_estimate > 0:
                required = input_token_estimate + output_budget
                if required > safe_context:
                    continue
            elif requirements.min_context_window > 0:
                if model.context_window < requirements.min_context_window:
                    continue

            # Health & Quota checks
            health = self.health_manager.get_health(provider.id, model.id)
            if health in [HealthState.UNAVAILABLE, HealthState.RATE_LIMITED]:
                continue

            quota = self.quota_manager.get_quota_state(provider.id)
            if quota == QuotaState.EXHAUSTED:
                continue

            candidates.append((provider, model))

        return candidates
