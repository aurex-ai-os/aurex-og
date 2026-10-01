"""
large_task_processor.py  —  Phase 6

Handles tasks that exceed any single model's context window.

Staged pipeline:
  Map → Chunk → Analyze → Store → Retrieve → CrossReference → Synthesize → Verify

Each stage runs within bounded context.
Never puts the entire corpus into a single LLM call.

Example tasks:
  "Read these 500 PDFs."
  "Analyze this entire repository."
  "Compare 200 research papers."
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import List, Dict, Any, Callable, Optional

logger = logging.getLogger(__name__)

# Max characters per chunk sent to a single LLM call
DEFAULT_CHUNK_SIZE = 6000    # ~1500 tokens — safe for any model


@dataclass
class TaskChunk:
    chunk_id: int
    source: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChunkAnalysis:
    chunk_id: int
    source: str
    summary: str
    key_points: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)


@dataclass
class LargeTaskResult:
    task_id: str
    synthesis: str
    chunk_count: int
    analyses: List[ChunkAnalysis] = field(default_factory=list)
    cross_references: List[str] = field(default_factory=list)
    verification_notes: str = ""


class LargeTaskProcessor:
    """
    Orchestrates multi-stage processing of large corpora.

    The caller supplies a `llm_call` function with signature:
        llm_call(prompt: str) -> str
    which the processor uses for each bounded LLM sub-call.
    """

    def __init__(
        self,
        llm_call: Callable[[str], str],
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ):
        self.llm_call = llm_call
        self.chunk_size = chunk_size

    # ── Stage 1: Map ──────────────────────────────────────────────────────────
    def map_documents(self, documents: List[Dict[str, str]]) -> List[TaskChunk]:
        """
        Convert a list of {source, content} documents into flat TaskChunks.
        """
        chunks = []
        chunk_id = 0
        for doc in documents:
            source = doc.get("source", "unknown")
            content = doc.get("content", "")
            # Stage 2: Chunk
            for piece in self._chunk_text(content):
                chunks.append(TaskChunk(chunk_id=chunk_id, source=source, content=piece))
                chunk_id += 1
        logger.info(f"[LargeTaskProcessor] Mapped {len(documents)} docs → {len(chunks)} chunks")
        return chunks

    # ── Stage 2: Chunk ────────────────────────────────────────────────────────
    def _chunk_text(self, text: str) -> List[str]:
        """Split text into bounded pieces with 10 % overlap."""
        if not text:
            return []
        step = int(self.chunk_size * 0.9)
        pieces = []
        for i in range(0, len(text), step):
            pieces.append(text[i: i + self.chunk_size])
        return pieces

    # ── Stage 3: Analyze ─────────────────────────────────────────────────────
    def analyze_chunks(self, chunks: List[TaskChunk]) -> List[ChunkAnalysis]:
        """
        Run a bounded LLM call on each chunk to extract summary + key points.
        """
        analyses = []
        for chunk in chunks:
            prompt = (
                f"Analyze the following excerpt from '{chunk.source}'.\n"
                f"Provide:\n1. A 2-sentence summary.\n2. Up to 5 key points (bullet list).\n"
                f"3. Up to 5 important entities (names, terms, concepts).\n\n"
                f"EXCERPT:\n{chunk.content}"
            )
            try:
                response = self.llm_call(prompt)
            except Exception as e:
                logger.warning(f"[LargeTaskProcessor] Chunk {chunk.chunk_id} analysis failed: {e}")
                response = f"Analysis unavailable: {e}"

            # Parse response into structured fields (best-effort)
            lines = [l.strip() for l in response.splitlines() if l.strip()]
            summary = " ".join(lines[:2]) if lines else response[:200]
            key_points = [l.lstrip("-•*123456789. ") for l in lines[2:7] if l]
            entities = [l.lstrip("-•*123456789. ") for l in lines[7:12] if l]

            analyses.append(ChunkAnalysis(
                chunk_id=chunk.chunk_id,
                source=chunk.source,
                summary=summary,
                key_points=key_points,
                entities=entities,
            ))
            logger.debug(f"[LargeTaskProcessor] Analyzed chunk {chunk.chunk_id}/{len(chunks)}")

        return analyses

    # ── Stage 4: Store ────────────────────────────────────────────────────────
    def store_analyses(self, task_id: str, analyses: List[ChunkAnalysis]) -> str:
        """Persist analyses to disk. Returns path to store file."""
        import json
        store_dir = os.path.join(
            os.path.dirname(__file__), "..", "data", "large_task_store"
        )
        os.makedirs(store_dir, exist_ok=True)
        path = os.path.join(store_dir, f"{task_id}.json")
        with open(path, "w") as f:
            json.dump([a.__dict__ for a in analyses], f, indent=2)
        logger.info(f"[LargeTaskProcessor] Stored {len(analyses)} analyses → {path}")
        return path

    # ── Stage 5: Retrieve ─────────────────────────────────────────────────────
    def retrieve_relevant(self, analyses: List[ChunkAnalysis], query: str, top_k: int = 10) -> List[ChunkAnalysis]:
        """Simple keyword retrieval across stored analyses."""
        q = query.lower()
        scored = []
        for a in analyses:
            score = sum(1 for w in q.split() if w in (a.summary + " ".join(a.key_points)).lower())
            scored.append((score, a))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [a for _, a in scored[:top_k]]

    # ── Stage 6: CrossReference ───────────────────────────────────────────────
    def cross_reference(self, analyses: List[ChunkAnalysis]) -> List[str]:
        """Find common entities/themes across multiple chunk analyses."""
        from collections import Counter
        entity_count = Counter()
        for a in analyses:
            for e in a.entities:
                entity_count[e.lower()] += 1
        # Entities appearing in more than one chunk are cross-references
        cross_refs = [entity for entity, count in entity_count.items() if count > 1]
        return sorted(cross_refs, key=lambda e: entity_count[e], reverse=True)[:20]

    # ── Stage 7: Synthesize ───────────────────────────────────────────────────
    def synthesize(
        self,
        relevant_analyses: List[ChunkAnalysis],
        cross_references: List[str],
        user_query: str,
    ) -> str:
        """Synthesize a final answer from relevant chunk analyses."""
        context_parts = []
        for a in relevant_analyses[:8]:  # Limit to 8 most relevant
            context_parts.append(
                f"[{a.source}] {a.summary}\nKey points: {'; '.join(a.key_points[:3])}"
            )
        context = "\n\n".join(context_parts)
        cross_ref_str = ", ".join(cross_references[:10]) if cross_references else "none"

        prompt = (
            f"Based on the following document analyses, answer the user's query.\n\n"
            f"USER QUERY: {user_query}\n\n"
            f"COMMON THEMES: {cross_ref_str}\n\n"
            f"RELEVANT EXCERPTS:\n{context}\n\n"
            f"Provide a comprehensive, well-structured answer."
        )
        return self.llm_call(prompt)

    # ── Stage 8: Verify ───────────────────────────────────────────────────────
    def verify(self, synthesis: str, user_query: str) -> str:
        """Ask the LLM to check the synthesis for completeness and accuracy."""
        prompt = (
            f"Review the following answer to this query: '{user_query}'\n\n"
            f"ANSWER:\n{synthesis}\n\n"
            f"Identify any gaps, unsupported claims, or missing critical information. "
            f"Keep your review concise (max 3 sentences)."
        )
        try:
            return self.llm_call(prompt)
        except Exception as e:
            return f"Verification skipped: {e}"

    # ── Full Pipeline ─────────────────────────────────────────────────────────
    def process(
        self,
        task_id: str,
        documents: List[Dict[str, str]],
        user_query: str,
    ) -> LargeTaskResult:
        """Run the full Map→Chunk→Analyze→Store→Retrieve→XRef→Synthesize→Verify pipeline."""
        logger.info(f"[LargeTaskProcessor] Starting pipeline task_id={task_id} docs={len(documents)}")

        chunks = self.map_documents(documents)
        analyses = self.analyze_chunks(chunks)
        self.store_analyses(task_id, analyses)
        relevant = self.retrieve_relevant(analyses, user_query)
        cross_refs = self.cross_reference(analyses)
        synthesis = self.synthesize(relevant, cross_refs, user_query)
        verification = self.verify(synthesis, user_query)

        return LargeTaskResult(
            task_id=task_id,
            synthesis=synthesis,
            chunk_count=len(chunks),
            analyses=analyses,
            cross_references=cross_refs,
            verification_notes=verification,
        )
