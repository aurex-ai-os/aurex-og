import pytest
from src.context_engine.models import ContextRequest, ContextItem, ContextSource, ContextScope
from src.context_engine.engine import ContextEngine
from src.context_engine.gatherers.legacy import LegacyMessagesGatherer

@pytest.mark.asyncio
async def test_context_engine_deduplication():
    # Setup legacy messages mimicking _build_route_request_state output
    messages = [
        {"role": "system", "content": "Active Document:\nThis is a unique test fact about Aurex.", "_agent_injected": "merged_prompt"},
        {"role": "system", "content": "Background knowledge:\nThis is a unique test fact about Aurex.", "_agent_injected": "context"}
    ]
    
    gatherer = LegacyMessagesGatherer(messages)
    engine = ContextEngine([gatherer])
    req = ContextRequest(owner="test")
    
    result = await engine.build_context(req, "claude-3-5-sonnet", token_budget=4000)
    
    final_messages = result["messages"]
    
    # Due to Deduplicator, the RAG chunk should be dropped because it's identical to Active Document
    content_str = str(final_messages)
    assert content_str.count("This is a unique test fact about Aurex.") == 1

@pytest.mark.asyncio
async def test_anthropic_renderer_empty_content():
    messages = [
        {"role": "assistant", "content": ""}
    ]
    
    gatherer = LegacyMessagesGatherer(messages)
    engine = ContextEngine([gatherer])
    req = ContextRequest(owner="test")
    
    result = await engine.build_context(req, "claude-3-5-sonnet", token_budget=4000)
    
    final_messages = result["messages"]
    # AnthropicRenderer should have rewritten empty content to "[Action selected]"
    assert final_messages[0]["content"] == "[Action selected]"
