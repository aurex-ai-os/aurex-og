from typing import List
from src.context_engine.models import ContextItem, ContextSource

class Deduplicator:
    def deduplicate(self, items: List[ContextItem]) -> List[ContextItem]:
        deduped = []
        sorted_items = sorted(items, key=lambda x: x.priority, reverse=True)
        
        active_doc_content = None
        for item in sorted_items:
            if item.source == ContextSource.ACTIVE_DOCUMENT:
                active_doc_content = item.content.lower()
                break
                
        for item in sorted_items:
            # Drop RAG chunks or background memory that are identical to Active Document
            if (item.source == ContextSource.RAG or "background knowledge" in item.content.lower()) and active_doc_content:
                # Basic sub-string check for overlapping content
                content_lower = item.content.lower().replace("background knowledge:", "").strip()
                if content_lower and content_lower in active_doc_content:
                    continue
            deduped.append(item)
            
        return deduped
