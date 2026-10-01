from typing import List, Dict, Any, Optional
from src.context_engine.models import ContextItem, ContextRequest, ContextSource, ContextScope
from src.context_engine.gatherers.base import ContextGatherer
from src.chat_processor import _content_tokens

class SystemGatherer(ContextGatherer):
    """Gathers the base system prompt and tool definitions."""
    def __init__(self, system_prompt: str, skill_index: str = ""):
        self.system_prompt = system_prompt
        self.skill_index = skill_index
        
    async def gather(self, request: ContextRequest) -> List[ContextItem]:
        items = []
        if self.system_prompt:
            items.append(ContextItem(
                id="system_prompt",
                source=ContextSource.SYSTEM_PROMPT,
                scope=ContextScope.SYSTEM,
                content=self.system_prompt,
                priority=100, # Highest priority, never dropped
                token_estimate=len(_content_tokens(self.system_prompt)),
                deduplication_key="system_prompt"
            ))
        if self.skill_index:
            items.append(ContextItem(
                id="skill_index",
                source=ContextSource.SKILL,
                scope=ContextScope.SYSTEM,
                content=self.skill_index,
                priority=90,
                token_estimate=len(_content_tokens(self.skill_index))
            ))
        return items

class DocumentGatherer(ContextGatherer):
    """Gathers the active document or email context."""
    def __init__(self, active_document_content: Optional[str] = None):
        self.active_document_content = active_document_content
        
    async def gather(self, request: ContextRequest) -> List[ContextItem]:
        if not self.active_document_content:
            return []
            
        return [ContextItem(
            id="active_document",
            source=ContextSource.ACTIVE_DOCUMENT,
            scope=ContextScope.TASK,
            content=self.active_document_content,
            priority=80,
            token_estimate=len(_content_tokens(self.active_document_content)),
            deduplication_key="active_document"
        )]

class ConversationGatherer(ContextGatherer):
    """Gathers the existing conversation history and tool observations."""
    def __init__(self, messages: List[Dict[str, Any]]):
        self.messages = messages
        
    async def gather(self, request: ContextRequest) -> List[ContextItem]:
        items = []
        for i, msg in enumerate(self.messages):
            # Ignore legacy injected system/preface messages to avoid duplication
            if msg.get("role") == "system" and msg.get("_agent_injected"):
                continue
                
            content_str = str(msg.get("content", ""))
            items.append(ContextItem(
                id=f"msg_{i}",
                source=ContextSource.TOOL_OUTPUT if msg.get("role") == "tool" else ContextSource.CONVERSATION_HISTORY,
                scope=ContextScope.TASK,
                content=content_str,
                priority=70 if msg.get("role") == "user" else 60,
                token_estimate=len(_content_tokens(content_str)),
                metadata={"raw_message": msg}
            ))
        return items
