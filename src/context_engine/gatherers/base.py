from abc import ABC, abstractmethod
from typing import List
from src.context_engine.models import ContextItem, ContextRequest

class ContextGatherer(ABC):
    @abstractmethod
    async def gather(self, request: ContextRequest) -> List[ContextItem]:
        """Gather context items for the given request."""
        pass
