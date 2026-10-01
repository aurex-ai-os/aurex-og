from typing import List
from src.context_engine.models import ContextItem, ContextRequest, ContextSource, ContextScope
from src.context_engine.gatherers.base import ContextGatherer
from src.chat_processor import _content_tokens

class RAGGatherer(ContextGatherer):
    def __init__(self, chat_processor):
        self.chat_processor = chat_processor
        
    async def gather(self, request: ContextRequest) -> List[ContextItem]:
        if not request.use_rag or request.incognito:
            return []
            
        # Temporarily use chat_processor's existing RAG retrieval to guarantee compatibility
        rag_text, sources = self.chat_processor._get_rag_context(
            request.message, 
            session=None, # session not strictly required for project scope if owner is used
            owner=request.owner
        )
        
        items = []
        if rag_text and sources:
            items.append(
                ContextItem(
                    id="rag_context",
                    source=ContextSource.RAG,
                    scope=ContextScope.PROJECT,
                    content=f"Background knowledge:\n{rag_text}",
                    priority=40,  # Lower priority than active document
                    token_estimate=len(_content_tokens(rag_text)),
                    metadata={"sources": sources}
                )
            )
        return items
