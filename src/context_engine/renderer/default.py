from typing import List, Dict, Any
from src.context_engine.models import ContextItem, ContextRequest, ContextSource
from src.context_engine.renderer.base import ContextRenderer

class DefaultRenderer(ContextRenderer):
    def render(self, items: List[ContextItem], request: ContextRequest) -> Dict[str, Any]:
        """
        Renders the ContextItems into a List of provider-agnostic message dicts.
        The agent loop handles provider-specific formatting right before the HTTP call.
        """
        system_content = []
        messages = []
        
        # Sort back to chronological/logical order
        # System items first, then history
        for item in sorted(items, key=lambda x: x.created_at if x.source == ContextSource.CONVERSATION_HISTORY else 0):
            if item.source in [ContextSource.SYSTEM_PROMPT, ContextSource.SKILL]:
                system_content.append(item.content)
            elif item.source == ContextSource.ACTIVE_DOCUMENT:
                system_content.append(f"Active Document:\n{item.content}")
            elif item.source == ContextSource.RAG:
                system_content.append(f"{item.content}")
            elif item.source == ContextSource.MEMORY:
                system_content.append(f"Memory:\n{item.content}")
            elif item.source == ContextSource.WEB_SEARCH:
                system_content.append(f"{item.content}")
            elif item.source in [ContextSource.CONVERSATION_HISTORY, ContextSource.TOOL_OUTPUT]:
                if "raw_message" in item.metadata:
                    messages.append(item.metadata["raw_message"])
                else:
                    # Fallback if raw message is missing
                    messages.append({"role": "system", "content": item.content})
                    
        # Construct the final array
        final_messages = []
        if system_content:
            final_messages.append({
                "role": "system",
                "content": "\n\n".join(system_content),
                "_agent_injected": "prompt"
            })
            
        final_messages.extend(messages)
        
        return {"messages": final_messages}
