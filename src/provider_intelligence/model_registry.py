from typing import Dict, List, Optional
from src.provider_intelligence.models import ModelDefinition

class ModelRegistry:
    def __init__(self):
        self._models: Dict[str, ModelDefinition] = {}
        
    def register_model(self, model: ModelDefinition):
        self._models[model.id] = model
        
    def get_model(self, model_id: str) -> Optional[ModelDefinition]:
        return self._models.get(model_id)
        
    def get_all_models(self) -> List[ModelDefinition]:
        return list(self._models.values())
        
    def get_models_by_provider(self, provider_id: str) -> List[ModelDefinition]:
        return [m for m in self._models.values() if m.provider_id == provider_id]
