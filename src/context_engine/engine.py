import asyncio
from typing import List, Dict, Any
import logging
from src.context_engine.models import ContextRequest, ContextItem
from src.context_engine.gatherers.base import ContextGatherer
from src.context_engine.deduplication import Deduplicator
from src.context_engine.budgeter import ContextBudgeter
from src.context_engine.renderer.factory import get_renderer

logger = logging.getLogger(__name__)

class ContextEngine:
    def __init__(
        self, 
        gatherers: List[ContextGatherer],
        deduplicator: Deduplicator = None,
        budgeter: ContextBudgeter = None
    ):
        self.gatherers = gatherers
        self.deduplicator = deduplicator or Deduplicator()
        self.budgeter = budgeter or ContextBudgeter()

    async def build_context(self, request: ContextRequest, model: str, token_budget: int = 0) -> Dict[str, Any]:
        """Full context pipeline for the active turn."""
        items = await self.gather_context(request)
        
        items = self.deduplicator.deduplicate(items)
            
        items = self.budgeter.apply_budget(items, token_budget)
            
        renderer = get_renderer(model)
        return renderer.render(items, request)

    async def gather_context(self, request: ContextRequest) -> List[ContextItem]:
        """Execute all gatherers concurrently."""
        tasks = [gatherer.gather(request) for gatherer in self.gatherers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        items = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Gatherer {self.gatherers[i].__class__.__name__} failed: {result}")
            elif result:
                items.extend(result)
        return items
