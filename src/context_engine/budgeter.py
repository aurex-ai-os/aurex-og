from typing import List
from src.context_engine.models import ContextItem, ContextSource
from src.context_compactor import trim_for_context

class ContextBudgeter:
    def __init__(self, soft_budget: int = 0):
        self.soft_budget = soft_budget

    def apply_budget(self, items: List[ContextItem], max_tokens: int) -> List[ContextItem]:
        """
        Drop lower-priority context items if the budget is exceeded.
        Uses trim_for_context for conversation history trimming.
        """
        budget = self.soft_budget if self.soft_budget > 0 else max_tokens
        if budget <= 0:
            return items
            
        # Group items
        history_items = []
        static_items = []
        
        for item in items:
            if item.source in [ContextSource.CONVERSATION_HISTORY, ContextSource.TOOL_OUTPUT]:
                history_items.append(item)
            else:
                static_items.append(item)
                
        # Sort static items by priority
        static_items = sorted(static_items, key=lambda x: x.priority, reverse=True)
        
        budgeted_static = []
        current_tokens = 0
        
        for item in static_items:
            if item.token_estimate <= 0:
                item.token_estimate = len(item.content) // 4
                
            if current_tokens + item.token_estimate <= budget:
                budgeted_static.append(item)
                current_tokens += item.token_estimate
            else:
                if item.priority >= 90:  # e.g., System prompt
                    budgeted_static.append(item)
                    current_tokens += item.token_estimate
                    
        # Now we have remaining budget for history
        remaining_budget = max(0, budget - current_tokens)
        
        if history_items:
            # We reconstruct the raw messages to pass to trim_for_context
            raw_messages = []
            for h in sorted(history_items, key=lambda x: x.id):
                if "raw_message" in h.metadata:
                    raw_messages.append(h.metadata["raw_message"])
                else:
                    raw_messages.append({"role": "system", "content": h.content})
                    
            trimmed_messages = trim_for_context(raw_messages, remaining_budget)
            
            # Convert trimmed back to ContextItems
            budgeted_history = []
            for i, msg in enumerate(trimmed_messages):
                content_str = str(msg.get("content", ""))
                budgeted_history.append(ContextItem(
                    id=f"msg_trimmed_{i}",
                    source=ContextSource.TOOL_OUTPUT if msg.get("role") == "tool" else ContextSource.CONVERSATION_HISTORY,
                    scope=history_items[0].scope,
                    content=content_str,
                    priority=history_items[0].priority,
                    token_estimate=len(content_str) // 4,
                    metadata={"raw_message": msg}
                ))
                
            budgeted_static.extend(budgeted_history)
            
        return budgeted_static
