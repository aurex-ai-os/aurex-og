"""
tool_observation_store.py  —  Phase 5

Large tool outputs must NOT be placed wholesale into conversation history.
This module stores full artifacts locally and injects only a compact
summary + preview into the message stream.

BAD:  Tool → 200K tokens → conversation history → LLM
GOOD: Tool → Artifact Store → Summary → Context Engine → LLM
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

_STORE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "tool_observations")

PREVIEW_CHARS = 800          # How many chars of raw output to include as preview
SUMMARY_MAX_CHARS = 300      # Max chars for the 1-line summary injected into history


@dataclass
class ToolObservation:
    tool_call_id: str
    source: str                        # e.g. "bash", "web_fetch", "read_file"
    summary: str                       # Short (≤300 chars) plain-text summary
    key_facts: List[str] = field(default_factory=list)
    structured_metadata: Dict[str, Any] = field(default_factory=dict)
    references: List[str] = field(default_factory=list)
    artifact_path: Optional[str] = None   # Path to full artifact on disk
    token_estimate: int = 0
    truncated_preview: str = ""        # First PREVIEW_CHARS chars of raw output

    def to_context_message(self) -> str:
        """Compact representation safe to inject into conversation history."""
        parts = [f"[Tool: {self.source}] {self.summary}"]
        if self.key_facts:
            parts.append("Key facts: " + "; ".join(self.key_facts[:5]))
        if self.truncated_preview:
            parts.append(f"Preview:\n{self.truncated_preview}")
        if self.artifact_path:
            parts.append(f"[Full output stored at: {self.artifact_path}]")
        return "\n".join(parts)


class ToolObservationStore:
    """
    Stores large tool outputs as local artifacts and exposes compact summaries.
    """

    def __init__(self, store_dir: str = _STORE_DIR):
        self.store_dir = store_dir
        os.makedirs(store_dir, exist_ok=True)
        self._index: Dict[str, ToolObservation] = {}

    def _artifact_path(self, tool_call_id: str) -> str:
        safe = hashlib.sha256(tool_call_id.encode()).hexdigest()[:16]
        return os.path.join(self.store_dir, f"{safe}.txt")

    def store(self, raw_output: str, tool_call_id: str, source: str = "tool") -> ToolObservation:
        """
        Store a (potentially huge) tool output.
        Returns a ToolObservation with summary + preview safe for history injection.
        """
        # Estimate tokens (rough: chars / 4)
        token_estimate = max(1, len(raw_output) // 4)

        # Write full artifact to disk
        artifact_path = self._artifact_path(tool_call_id)
        try:
            with open(artifact_path, "w", encoding="utf-8", errors="replace") as f:
                f.write(raw_output)
        except Exception as e:
            logger.warning(f"[ToolObservationStore] Could not write artifact: {e}")
            artifact_path = None

        # Build compact summary
        first_line = (raw_output.strip().splitlines() or [""])[0][:SUMMARY_MAX_CHARS]
        summary = first_line if first_line else f"Tool output ({token_estimate} tokens)"

        # Key facts: first 5 non-empty lines
        key_facts = [
            line.strip() for line in raw_output.splitlines()
            if line.strip()
        ][:5]

        obs = ToolObservation(
            tool_call_id=tool_call_id,
            source=source,
            summary=summary,
            key_facts=key_facts,
            token_estimate=token_estimate,
            artifact_path=artifact_path,
            truncated_preview=raw_output[:PREVIEW_CHARS],
        )
        self._index[tool_call_id] = obs
        logger.debug(
            f"[ToolObservationStore] Stored {source} output: "
            f"{token_estimate} tokens → {artifact_path}"
        )
        return obs

    def get_preview(self, tool_call_id: str) -> str:
        """Return the compact context-safe representation."""
        obs = self._index.get(tool_call_id)
        if obs:
            return obs.to_context_message()
        # Try loading from disk index
        return f"[Tool output {tool_call_id} not found in store]"

    def get_full(self, tool_call_id: str) -> Optional[str]:
        """Return the full raw artifact content."""
        obs = self._index.get(tool_call_id)
        if obs and obs.artifact_path and os.path.exists(obs.artifact_path):
            try:
                with open(obs.artifact_path, "r", encoding="utf-8", errors="replace") as f:
                    return f.read()
            except Exception as e:
                logger.warning(f"[ToolObservationStore] Could not read artifact: {e}")
        return None

    def retrieve_relevant(self, query: str, top_k: int = 3) -> List[ToolObservation]:
        """
        Simple keyword-match retrieval across stored observations.
        In production this could be replaced by vector similarity search.
        """
        q = query.lower()
        scored = []
        for obs in self._index.values():
            score = 0
            score += sum(1 for w in q.split() if w in obs.summary.lower())
            score += sum(1 for fact in obs.key_facts if any(w in fact.lower() for w in q.split()))
            scored.append((score, obs))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [obs for _, obs in scored[:top_k] if _ > 0]


# Module-level singleton for easy import
_default_store: Optional[ToolObservationStore] = None


def get_store() -> ToolObservationStore:
    global _default_store
    if _default_store is None:
        _default_store = ToolObservationStore()
    return _default_store
