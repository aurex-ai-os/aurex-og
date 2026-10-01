from typing import List, Dict, Any
from src.context_engine.models import ContextItem, ContextRequest, ContextSource
from src.context_engine.renderer.default import DefaultRenderer

class AnthropicRenderer(DefaultRenderer):
    def render(self, items: List[ContextItem], request: ContextRequest) -> Dict[str, Any]:
        result = super().render(items, request)
        messages = result["messages"]
        
        # Strip reasoning content and handle empty content
        for msg in messages:
            if msg.get("role") == "assistant":
                # Anthropic rejects empty content for non-final messages
                if not msg.get("content"):
                    msg["content"] = "[Action selected]"
                    
                # Strip out deepseek-style reasoning content if it leaked in
                if "reasoning_content" in msg:
                    del msg["reasoning_content"]
                    
        return result
