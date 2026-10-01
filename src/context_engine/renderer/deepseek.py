from typing import List, Dict, Any
from src.context_engine.models import ContextItem, ContextRequest, ContextSource
from src.context_engine.renderer.default import DefaultRenderer

class DeepSeekRenderer(DefaultRenderer):
    def render(self, items: List[ContextItem], request: ContextRequest) -> Dict[str, Any]:
        result = super().render(items, request)
        messages = result["messages"]
        
        # DeepSeek: Preserve reasoning_content
        # No structural changes needed beyond DefaultRenderer, but we can enforce
        # that reasoning_content only exists on the MOST RECENT assistant turn if required.
        return result
