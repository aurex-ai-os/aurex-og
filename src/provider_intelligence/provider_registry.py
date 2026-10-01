from typing import Dict, List, Optional
from src.provider_intelligence.models import ProviderDefinition, ProviderType, PrivacyLevel

class ProviderRegistry:
    def __init__(self):
        self._providers: Dict[str, ProviderDefinition] = {}
        
    def register_provider(self, provider: ProviderDefinition):
        self._providers[provider.id] = provider
        
    def get_provider(self, provider_id: str) -> Optional[ProviderDefinition]:
        return self._providers.get(provider_id)
        
    def get_all_providers(self) -> List[ProviderDefinition]:
        return list(self._providers.values())
        
    def get_enabled_providers(self) -> List[ProviderDefinition]:
        return [p for p in self._providers.values() if p.is_enabled]

