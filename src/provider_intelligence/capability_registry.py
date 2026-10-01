"""
capability_registry.py

Normalizes and maps model names or provider IDs to capabilities.
Uses a curated known-models database first, then falls back to heuristic ID parsing.
"""

from typing import Set, Dict
from src.provider_intelligence.models import Capability

# ── Curated known-model capability table ──────────────────────────────────────
# Keys: lowercase model ID substrings. Matched in order (most specific first).
# This avoids breaking on new model IDs not covered by string heuristics.
_KNOWN_MODELS: Dict[str, Set[Capability]] = {
    # OpenAI
    "gpt-4o": {
        Capability.TEXT_GENERATION, Capability.STREAMING, Capability.VISION,
        Capability.TOOL_CALLING, Capability.STRUCTURED_OUTPUT, Capability.JSON_MODE,
        Capability.LONG_CONTEXT,
    },
    "gpt-4-turbo": {
        Capability.TEXT_GENERATION, Capability.STREAMING, Capability.VISION,
        Capability.TOOL_CALLING, Capability.STRUCTURED_OUTPUT, Capability.JSON_MODE,
        Capability.LONG_CONTEXT,
    },
    "gpt-4": {
        Capability.TEXT_GENERATION, Capability.STREAMING,
        Capability.TOOL_CALLING, Capability.STRUCTURED_OUTPUT, Capability.JSON_MODE,
    },
    "gpt-3.5": {
        Capability.TEXT_GENERATION, Capability.STREAMING,
        Capability.TOOL_CALLING, Capability.JSON_MODE,
    },
    "o1-mini": {
        Capability.TEXT_GENERATION, Capability.STREAMING, Capability.REASONING,
    },
    "o1-preview": {
        Capability.TEXT_GENERATION, Capability.STREAMING, Capability.REASONING,
        Capability.LONG_CONTEXT,
    },
    "o1": {
        Capability.TEXT_GENERATION, Capability.STREAMING, Capability.REASONING,
        Capability.LONG_CONTEXT, Capability.VISION,
    },
    "o3": {
        Capability.TEXT_GENERATION, Capability.STREAMING, Capability.REASONING,
        Capability.LONG_CONTEXT, Capability.VISION, Capability.TOOL_CALLING,
    },
    # Anthropic Claude
    "claude-3-5-sonnet": {
        Capability.TEXT_GENERATION, Capability.STREAMING, Capability.VISION,
        Capability.TOOL_CALLING, Capability.STRUCTURED_OUTPUT, Capability.LONG_CONTEXT,
    },
    "claude-3-5-haiku": {
        Capability.TEXT_GENERATION, Capability.STREAMING, Capability.VISION,
        Capability.TOOL_CALLING, Capability.STRUCTURED_OUTPUT,
    },
    "claude-3-opus": {
        Capability.TEXT_GENERATION, Capability.STREAMING, Capability.VISION,
        Capability.TOOL_CALLING, Capability.STRUCTURED_OUTPUT, Capability.LONG_CONTEXT,
    },
    "claude-3-sonnet": {
        Capability.TEXT_GENERATION, Capability.STREAMING, Capability.VISION,
        Capability.TOOL_CALLING, Capability.LONG_CONTEXT,
    },
    "claude-3-haiku": {
        Capability.TEXT_GENERATION, Capability.STREAMING, Capability.VISION,
        Capability.TOOL_CALLING,
    },
    # Google Gemini
    "gemini-2.0-flash": {
        Capability.TEXT_GENERATION, Capability.STREAMING, Capability.VISION,
        Capability.TOOL_CALLING, Capability.STRUCTURED_OUTPUT, Capability.LONG_CONTEXT,
    },
    "gemini-1.5-pro": {
        Capability.TEXT_GENERATION, Capability.STREAMING, Capability.VISION,
        Capability.TOOL_CALLING, Capability.STRUCTURED_OUTPUT, Capability.LONG_CONTEXT,
    },
    "gemini-1.5-flash": {
        Capability.TEXT_GENERATION, Capability.STREAMING, Capability.VISION,
        Capability.TOOL_CALLING, Capability.LONG_CONTEXT,
    },
    # Meta Llama
    "llama-3.3": {
        Capability.TEXT_GENERATION, Capability.STREAMING, Capability.TOOL_CALLING,
    },
    "llama-3.2": {
        Capability.TEXT_GENERATION, Capability.STREAMING, Capability.VISION,
        Capability.TOOL_CALLING,
    },
    "llama-3.1": {
        Capability.TEXT_GENERATION, Capability.STREAMING, Capability.TOOL_CALLING,
        Capability.LONG_CONTEXT,
    },
    "llama-3": {
        Capability.TEXT_GENERATION, Capability.STREAMING,
    },
    # Mistral
    "mixtral": {
        Capability.TEXT_GENERATION, Capability.STREAMING, Capability.TOOL_CALLING,
    },
    "mistral-large": {
        Capability.TEXT_GENERATION, Capability.STREAMING, Capability.TOOL_CALLING,
        Capability.STRUCTURED_OUTPUT,
    },
    "mistral-nemo": {
        Capability.TEXT_GENERATION, Capability.STREAMING,
    },
    # DeepSeek
    "deepseek-r1": {
        Capability.TEXT_GENERATION, Capability.STREAMING, Capability.REASONING,
        Capability.LONG_CONTEXT,
    },
    "deepseek-v3": {
        Capability.TEXT_GENERATION, Capability.STREAMING, Capability.TOOL_CALLING,
        Capability.LONG_CONTEXT,
    },
    "deepseek-coder": {
        Capability.TEXT_GENERATION, Capability.STREAMING, Capability.TOOL_CALLING,
    },
    # Qwen
    "qwen2.5": {
        Capability.TEXT_GENERATION, Capability.STREAMING, Capability.TOOL_CALLING,
        Capability.LONG_CONTEXT,
    },
    "qwq": {
        Capability.TEXT_GENERATION, Capability.STREAMING, Capability.REASONING,
    },
}


class CapabilityRegistry:
    """Normalizes and maps model names or provider IDs to capabilities."""

    def __init__(self):
        self._manual_overrides: Dict[str, Set[Capability]] = {}

    def guess_capabilities(self, model_id: str, is_local: bool = False) -> Set[Capability]:
        """
        Resolve capabilities for a model.

        Priority order:
        1. Manual overrides (highest confidence)
        2. Curated known-models table (substring match, most specific first)
        3. Heuristic string pattern matching (lowest confidence, fallback only)
        """
        # 1. Manual override
        if model_id in self._manual_overrides:
            return self._manual_overrides[model_id]

        lower_id = model_id.lower()

        # 2. Curated known-models table (longest matching key wins)
        matched_key = None
        matched_len = 0
        for key, caps in _KNOWN_MODELS.items():
            if key in lower_id and len(key) > matched_len:
                matched_key = key
                matched_len = len(key)

        if matched_key:
            caps = set(_KNOWN_MODELS[matched_key])
            if is_local:
                caps.add(Capability.LOCAL_EXECUTION)
            return caps

        # 3. Heuristic fallback for completely unknown models
        caps: Set[Capability] = {Capability.TEXT_GENERATION, Capability.STREAMING}

        if is_local:
            caps.add(Capability.LOCAL_EXECUTION)

        # Vision
        if any(t in lower_id for t in ("vision", "-vl", ":vl", "-vision", "pixtral", "llava")):
            caps.add(Capability.VISION)

        # Tool calling
        if any(t in lower_id for t in ("tool", "-fc", ":fc", "function", "hermes", "instruct")):
            caps.add(Capability.TOOL_CALLING)

        # Reasoning
        if any(t in lower_id for t in ("reasoning", "r1", "o1", "o3", "qwq", "thinking")):
            caps.add(Capability.REASONING)

        # Structured output / JSON
        if any(t in lower_id for t in ("json", "structured")):
            caps.add(Capability.STRUCTURED_OUTPUT)
            caps.add(Capability.JSON_MODE)

        # Long context
        if any(t in lower_id for t in ("128k", "200k", "1m", "long", "extended")):
            caps.add(Capability.LONG_CONTEXT)

        return caps

    def get_capabilities(self, model_id: str, is_local: bool = False) -> Set[Capability]:
        return self.guess_capabilities(model_id, is_local)

    def set_override(self, model_id: str, capabilities: Set[Capability]):
        """Manually set authoritative capabilities for a specific model ID."""
        self._manual_overrides[model_id] = capabilities

    def is_known_model(self, model_id: str) -> bool:
        """Returns True if the model is in the curated table (high-confidence data)."""
        lower_id = model_id.lower()
        return any(key in lower_id for key in _KNOWN_MODELS)
