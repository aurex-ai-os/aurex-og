"""
context_waterfall.py  —  Phase 4

9-level waterfall for reducing context size before routing.
The user must NEVER receive "context window too large" if the waterfall can handle it.

Level 0: Direct send   — fits as-is
Level 1: Dedup         — remove consecutive duplicate messages
Level 2: System trim   — truncate system prompt to essential instructions
Level 3: Old compress  — summarise old messages to 1-sentence each
Level 4: Sliding win   — keep only most-recent messages that fit
Level 5: Tool trim     — reduce tool_output messages to summaries
Level 6: Split flag    — request must be split into independent subtasks
Level 7: Multi-model   — flag for multi-model aggregation
Level 8: Larger model  — flag to select a model with bigger context window
Level 9: Multi-pass    — flag for multi-pass synthesis strategy
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from src.context_engine.context_admission import (
    estimate_input_tokens,
    safe_context_limit,
    SAFETY_MARGIN,
)

logger = logging.getLogger(__name__)


@dataclass
class WaterfallResult:
    messages: List[Dict[str, Any]]
    level_reached: int
    strategy: str
    input_tokens_after: int
    # Special flags for levels 6-9
    needs_split: bool = False
    needs_multi_model: bool = False
    needs_larger_model: bool = False
    needs_multi_pass: bool = False
    exhausted: bool = False


def _fits(messages: List[Dict[str, Any]], context_window: int, output_budget: int) -> bool:
    tokens = estimate_input_tokens(messages)
    return (tokens + output_budget) <= safe_context_limit(context_window, SAFETY_MARGIN)


def _dedup(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Level 1: remove consecutive identical messages."""
    result = []
    for msg in messages:
        if result and result[-1].get("content") == msg.get("content") and result[-1].get("role") == msg.get("role"):
            continue
        result.append(msg)
    return result


def _trim_system(messages: List[Dict[str, Any]], max_chars: int = 1000) -> List[Dict[str, Any]]:
    """Level 2: truncate system prompt."""
    result = []
    for msg in messages:
        if msg.get("role") == "system":
            content = str(msg.get("content", ""))
            if len(content) > max_chars:
                msg = {**msg, "content": content[:max_chars] + "\n[...system prompt truncated for context...]"}
        result.append(msg)
    return result


def _compress_old(messages: List[Dict[str, Any]], keep_recent: int = 6) -> List[Dict[str, Any]]:
    """Level 3: compress older messages to 1-line summaries."""
    if len(messages) <= keep_recent:
        return messages
    old = messages[:-keep_recent]
    recent = messages[-keep_recent:]
    compressed = []
    for msg in old:
        if msg.get("role") in ("user", "assistant"):
            content = str(msg.get("content", ""))
            summary = content[:120].replace("\n", " ") + ("..." if len(content) > 120 else "")
            compressed.append({**msg, "content": f"[Summary] {summary}"})
        else:
            compressed.append(msg)
    return compressed + recent


def _sliding_window(
    messages: List[Dict[str, Any]],
    context_window: int,
    output_budget: int,
) -> List[Dict[str, Any]]:
    """Level 4: keep only the most-recent messages that fit."""
    # Always keep system message if present
    system = [m for m in messages if m.get("role") == "system"]
    rest = [m for m in messages if m.get("role") != "system"]
    for i in range(len(rest), 0, -1):
        candidate = system + rest[-i:]
        if _fits(candidate, context_window, output_budget):
            return candidate
    return system + rest[-1:]  # bare minimum


def _trim_tool_outputs(messages: List[Dict[str, Any]], max_tool_chars: int = 500) -> List[Dict[str, Any]]:
    """Level 5: truncate large tool output messages."""
    result = []
    for msg in messages:
        if msg.get("role") == "tool" or (msg.get("role") == "user" and "tool_result" in str(msg.get("content", ""))):
            content = str(msg.get("content", ""))
            if len(content) > max_tool_chars:
                msg = {**msg, "content": content[:max_tool_chars] + "\n[...tool output truncated...]"}
        result.append(msg)
    return result


def run_waterfall(
    messages: List[Dict[str, Any]],
    context_window: int,
    output_budget: int = 4096,
) -> WaterfallResult:
    """
    Run the context waterfall and return the best reducible message list.
    Never raises — always returns a WaterfallResult indicating what happened.
    """

    # Level 0: fits as-is
    if _fits(messages, context_window, output_budget):
        return WaterfallResult(
            messages=messages,
            level_reached=0,
            strategy="DIRECT",
            input_tokens_after=estimate_input_tokens(messages),
        )

    logger.info(f"[Waterfall] Starting waterfall for context_window={context_window}")

    # Level 1: dedup
    msgs = _dedup(messages)
    if _fits(msgs, context_window, output_budget):
        logger.info("[Waterfall] Level 1 (dedup) sufficient")
        return WaterfallResult(msgs, 1, "DEDUP", estimate_input_tokens(msgs))

    # Level 2: system trim
    msgs = _trim_system(msgs)
    if _fits(msgs, context_window, output_budget):
        logger.info("[Waterfall] Level 2 (system trim) sufficient")
        return WaterfallResult(msgs, 2, "SYSTEM_TRIM", estimate_input_tokens(msgs))

    # Level 3: compress old messages
    msgs = _compress_old(msgs)
    if _fits(msgs, context_window, output_budget):
        logger.info("[Waterfall] Level 3 (compress old) sufficient")
        return WaterfallResult(msgs, 3, "COMPRESS_OLD", estimate_input_tokens(msgs))

    # Level 4: sliding window
    msgs = _sliding_window(msgs, context_window, output_budget)
    if _fits(msgs, context_window, output_budget):
        logger.info("[Waterfall] Level 4 (sliding window) sufficient")
        return WaterfallResult(msgs, 4, "SLIDING_WINDOW", estimate_input_tokens(msgs))

    # Level 5: trim tool outputs
    msgs = _trim_tool_outputs(msgs)
    if _fits(msgs, context_window, output_budget):
        logger.info("[Waterfall] Level 5 (tool trim) sufficient")
        return WaterfallResult(msgs, 5, "TOOL_TRIM", estimate_input_tokens(msgs))

    # Level 6: split flag
    logger.info("[Waterfall] Level 6: flagging for subtask split")
    result = WaterfallResult(msgs, 6, "NEEDS_SPLIT", estimate_input_tokens(msgs), needs_split=True)
    return result

    # Level 7-9 are handled by the orchestrator receiving needs_split=True
    # and deciding whether to use multi-model, larger model, or multi-pass.
