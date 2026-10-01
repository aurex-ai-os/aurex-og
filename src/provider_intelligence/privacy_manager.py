from src.provider_intelligence.models import PrivacyLevel, ProviderDefinition, ModelDefinition, TaskRequirements

class PrivacyManager:
    @staticmethod
    def is_provider_allowed(task_req: TaskRequirements, provider: ProviderDefinition, model: ModelDefinition) -> bool:
        req_privacy = task_req.privacy_requirement
        
        if req_privacy == PrivacyLevel.LOCAL_ONLY:
            return provider.is_local and model.is_local
            
        if req_privacy == PrivacyLevel.NO_EXTERNAL_SERVICE:
            return provider.privacy_level in [PrivacyLevel.LOCAL_ONLY, PrivacyLevel.NO_EXTERNAL_SERVICE]
            
        if task_req.requires_local and not (provider.is_local and model.is_local):
            return False
            
        return True
