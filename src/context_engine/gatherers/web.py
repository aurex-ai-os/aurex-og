from typing import List
from src.context_engine.models import ContextItem, ContextRequest, ContextSource, ContextScope
from src.context_engine.gatherers.base import ContextGatherer
from src.chat_processor import _content_tokens

class WebGatherer(ContextGatherer):
    def __init__(self, chat_processor):
        self.chat_processor = chat_processor
        
    async def gather(self, request: ContextRequest) -> List[ContextItem]:
        if not request.use_web:
            return []
            
        web_text, sources = await self.chat_processor._get_web_context(
            request.message, 
            time_filter=request.time_filter
        )
        
        items = []
        if web_text and sources:
            items.append(
                ContextItem(
                    id="web_context",
                    source=ContextSource.WEB_SEARCH,
                    scope=ContextScope.TASK,
                    content=f"Web Search Results:\n{web_text}",
                    priority=45,
                    token_estimate=len(_content_tokens(web_text)),
                    metadata={"sources": sources}
                )
            )
        return items
