from typing import List, Dict, Any
from src.context_engine.models import ContextItem, ContextRequest, ContextSource
from src.context_engine.renderer.default import DefaultRenderer

class GeminiRenderer(DefaultRenderer):
    def render(self, items: List[ContextItem], request: ContextRequest) -> Dict[str, Any]:
        result = super().render(items, request)
        messages = result["messages"]
        
        # Gemini handles extra_content (opaque tool structures)
        # The history messages from the agent loop already contain extra_content.
        # We ensure it's preserved.
        return result
