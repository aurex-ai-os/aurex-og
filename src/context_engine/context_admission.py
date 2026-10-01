"""
context_admission.py  —  Phase 3

Pre-flight guard: estimate how many tokens a request needs, compare against
the VERIFIED model context window (with safety margin), and reject / flag the
request BEFORE it is sent upstream.

Never rely on upstream failure to discover a context limit.
"""

from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

SAFETY_MARGIN = 0.92          # Never fill more than 92 % of a context window
PROTOCOL_OVERHEAD = 200       # Estimated tokens consumed by OpenAI protocol framing


class ContextAdmissionError(Exception):
    """Raised when a request cannot fit in any available model context window."""
    def __init__(self, message: str, required: int, available: int):
        super().__init__(message)
        self.required = required
        self.available = available


def estimate_input_tokens(messages: List[Dict[str, Any]]) -> int:
    """
    Estimate the token count of a messages array.

    Uses tiktoken (cl100k_base) when available; falls back to len(text) // 4
    which is the standard rule-of-thumb for English prose.

    This is an ESTIMATE — do not treat it as exact. The caller should add a
    safety margin on top.
    """
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        total = 0
        for msg in messages:
            # Each message costs ~4 tokens for role/framing in the OpenAI protocol
            total += 4
            content = msg.get("content") or ""
            if isinstance(content, list):
                # Multi-modal message — concatenate text parts
                content = " ".join(
                    p.get("text", "") for p in content if isinstance(p, dict)
                )
            total += len(enc.encode(str(content)))
        return total
    except Exception:
        # Fallback: char / 4
        raw = " ".join(
            str(m.get("content", "")) for m in messages
        )
        return max(1, len(raw) // 4)


def calculate_required_context(
    input_tokens: int,
    output_budget: int = 4096,
    reasoning_budget: int = 0,
    overhead: int = PROTOCOL_OVERHEAD,
) -> int:
    """Return the total context slots required for this request."""
    return input_tokens + output_budget + reasoning_budget + overhead


def safe_context_limit(model_context_window: int, safety: float = SAFETY_MARGIN) -> int:
    """Return the usable context slots (context_window * safety_margin)."""
    return int(model_context_window * safety)


def can_fit(
    model_context_window: int,
    required_context: int,
    safety: float = SAFETY_MARGIN,
) -> bool:
    """Return True if the request fits inside the model's safe context limit."""
    return required_context <= safe_context_limit(model_context_window, safety)


def admit_or_raise(
    messages: List[Dict[str, Any]],
    model_context_window: int,
    output_budget: int = 4096,
    reasoning_budget: int = 0,
    model_id: str = "unknown",
) -> Dict[str, int]:
    """
    Run context admission for a request.

    Returns a dict with token accounting info on success.
    Raises ContextAdmissionError if the request cannot possibly fit.
    """
    input_tokens = estimate_input_tokens(messages)
    required = calculate_required_context(input_tokens, output_budget, reasoning_budget)
    safe_limit = safe_context_limit(model_context_window)

    info = {
        "input_tokens": input_tokens,
        "output_budget": output_budget,
        "reasoning_budget": reasoning_budget,
        "required": required,
        "safe_limit": safe_limit,
        "model_context_window": model_context_window,
        "fits": required <= safe_limit,
    }

    if not info["fits"]:
        logger.warning(
            f"[ContextAdmission] REJECTED: model={model_id} "
            f"required={required} safe_limit={safe_limit} "
            f"input={input_tokens} output_budget={output_budget}"
        )
        raise ContextAdmissionError(
            f"Request requires {required} tokens but model '{model_id}' "
            f"safe limit is {safe_limit} (context_window={model_context_window})",
            required=required,
            available=safe_limit,
        )

    logger.debug(
        f"[ContextAdmission] ADMITTED: model={model_id} "
        f"required={required}/{safe_limit} ({required/safe_limit*100:.1f}%)"
    )
    return info
