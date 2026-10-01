from typing import List, Dict, Any
from src.context_engine.models import ContextItem, ContextRequest, ContextSource, ContextScope
from src.context_engine.gatherers.base import ContextGatherer
from src.chat_processor import _content_tokens

class LegacyMessagesGatherer(ContextGatherer):
    """Parses a pre-assembled legacy messages array into proper ContextItems."""
    def __init__(self, messages: List[Dict[str, Any]]):
        self.messages = messages
        
    async def gather(self, request: ContextRequest) -> List[ContextItem]:
        items = []
        for i, msg in enumerate(self.messages):
            role = msg.get("role", "")
            injected = msg.get("_agent_injected", "")
            protected = msg.get("_protected", False)
            content = str(msg.get("content", ""))
            
            source = ContextSource.CONVERSATION_HISTORY
            scope = ContextScope.TASK
            priority = 60
            
            if role == "system":
                if "Active Document" in content or "Editing:" in content:
                    source = ContextSource.ACTIVE_DOCUMENT
                    scope = ContextScope.TASK
                    priority = 80
                elif "Background knowledge:" in content:
                    source = ContextSource.RAG
                    scope = ContextScope.PROJECT
                    priority = 40
                elif injected == "context" or (protected and "Memory" in content):
                    source = ContextSource.MEMORY
                    scope = ContextScope.USER
                    priority = 70
                elif injected in ["prompt", "merged_prompt"]:
                    source = ContextSource.SYSTEM_PROMPT
                    scope = ContextScope.SYSTEM
                    priority = 100
                else:
                    source = ContextSource.SYSTEM_PROMPT
                    scope = ContextScope.TASK
                    priority = 90
            elif role == "tool":
                source = ContextSource.TOOL_OUTPUT
                scope = ContextScope.TASK
                priority = 50
            elif role == "user":
                source = ContextSource.CONVERSATION_HISTORY
                scope = ContextScope.TASK
                priority = 65
                
            items.append(ContextItem(
                id=f"legacy_{i}",
                source=source,
                scope=scope,
                content=content,
                priority=priority,
                token_estimate=len(_content_tokens(content)),
                metadata={"raw_message": msg}
            ))
        return items
