import logging
from typing import List, Optional
from src.context_engine.models import ContextItem, ContextRequest, ContextSource, ContextScope
from src.context_engine.gatherers.base import ContextGatherer
from src.chat_processor import _content_tokens

logger = logging.getLogger(__name__)

class MemoryGatherer(ContextGatherer):
    def __init__(self, chat_processor):
        self.chat_processor = chat_processor
        
    async def gather(self, request: ContextRequest) -> List[ContextItem]:
        if not request.use_memory or request.incognito:
            return []
            
        # We use chat_processor._get_memory_context which internally calls MemoryManager
        # and handles pinned memory, limits, usage tracking, and relevance.
        memory_text, used_memories = self.chat_processor._get_memory_context(
            request.message,
            owner=request.owner
        )
        
        items = []
        if memory_text:
            items.append(
                ContextItem(
                    id="memory_context",
                    source=ContextSource.MEMORY,
                    scope=ContextScope.USER,
                    content=memory_text,
                    priority=70,  # Below active document, above conversation
                    token_estimate=len(_content_tokens(memory_text)),
                    metadata={"used_memories": used_memories}
                )
            )
        return items
