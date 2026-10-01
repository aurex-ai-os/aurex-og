from src.context_engine.renderer.default import DefaultRenderer
from src.context_engine.renderer.anthropic import AnthropicRenderer
from src.context_engine.renderer.gemini import GeminiRenderer
from src.context_engine.renderer.deepseek import DeepSeekRenderer

def get_renderer(model: str) -> 'ContextRenderer':
    model = (model or "").lower()
    if "claude" in model:
        return AnthropicRenderer()
    elif "gemini" in model:
        return GeminiRenderer()
    elif "deepseek" in model:
        return DeepSeekRenderer()
    return DefaultRenderer()
