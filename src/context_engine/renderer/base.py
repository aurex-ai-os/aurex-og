from abc import ABC, abstractmethod
from typing import List, Dict, Any
from src.context_engine.models import ContextItem, ContextRequest

class ContextRenderer(ABC):
    @abstractmethod
    def render(self, items: List[ContextItem], request: ContextRequest) -> Dict[str, Any]:
        pass
