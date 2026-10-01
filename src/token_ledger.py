"""
token_ledger.py  —  Phase 10

Unified per-request token accounting for all providers and provider pools.
Stored in SQLite using the existing Aurex database pattern.

NEVER logs: API keys, OAuth tokens, passwords, credentials, raw prompts.
"""

from __future__ import annotations

import logging
import time
from typing import Optional, Dict, Any, List

from sqlalchemy import Column, String, Integer, Float, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger(__name__)

Base = declarative_base()


class TokenLedgerEntry(Base):
    __tablename__ = "token_ledger"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(Float, nullable=False, index=True)
    session_id = Column(String(128), nullable=True, index=True)
    task_id = Column(String(128), nullable=True, index=True)
    model_id = Column(String(256), nullable=True, index=True)
    provider_id = Column(String(128), nullable=True, index=True)
    provider_pool = Column(String(64), nullable=True, index=True)

    # Token counts
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cached_tokens = Column(Integer, default=0)
    estimated_tokens = Column(Integer, default=0)
    actual_tokens = Column(Integer, default=0)
    context_tokens = Column(Integer, default=0)
    compression_savings = Column(Integer, default=0)
    retrieval_tokens = Column(Integer, default=0)
    tool_observation_tokens = Column(Integer, default=0)

    # Performance
    latency_ms = Column(Float, default=0.0)
    status = Column(String(32), default="ok")
    error_class = Column(String(64), nullable=True)


def _get_db_url() -> str:
    import os
    data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(data_dir, exist_ok=True)
    return f"sqlite:///{os.path.join(data_dir, 'token_ledger.db')}"


class TokenLedger:
    def __init__(self, db_url: Optional[str] = None):
        url = db_url or _get_db_url()
        self._engine = create_engine(url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(self._engine)
        self._Session = sessionmaker(bind=self._engine)

    def record(
        self,
        *,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
        model_id: Optional[str] = None,
        provider_id: Optional[str] = None,
        provider_pool: Optional[str] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cached_tokens: int = 0,
        estimated_tokens: int = 0,
        actual_tokens: int = 0,
        context_tokens: int = 0,
        compression_savings: int = 0,
        retrieval_tokens: int = 0,
        tool_observation_tokens: int = 0,
        latency_ms: float = 0.0,
        status: str = "ok",
        error_class: Optional[str] = None,
    ) -> None:
        """Record one request's token usage. Never logs secrets."""
        entry = TokenLedgerEntry(
            timestamp=time.time(),
            session_id=session_id,
            task_id=task_id,
            model_id=model_id,
            provider_id=provider_id,
            provider_pool=provider_pool,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            estimated_tokens=estimated_tokens,
            actual_tokens=actual_tokens,
            context_tokens=context_tokens,
            compression_savings=compression_savings,
            retrieval_tokens=retrieval_tokens,
            tool_observation_tokens=tool_observation_tokens,
            latency_ms=latency_ms,
            status=status,
            error_class=error_class,
        )
        with self._Session() as session:
            session.add(entry)
            session.commit()

    def get_stats(
        self,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
        model_id: Optional[str] = None,
        provider_id: Optional[str] = None,
        provider_pool: Optional[str] = None,
        day: Optional[str] = None,    # "YYYY-MM-DD"
        month: Optional[str] = None,  # "YYYY-MM"
    ) -> Dict[str, Any]:
        """Return aggregated token stats for the given filters."""
        with self._Session() as session:
            q = session.query(TokenLedgerEntry)
            if session_id:
                q = q.filter(TokenLedgerEntry.session_id == session_id)
            if task_id:
                q = q.filter(TokenLedgerEntry.task_id == task_id)
            if model_id:
                q = q.filter(TokenLedgerEntry.model_id == model_id)
            if provider_id:
                q = q.filter(TokenLedgerEntry.provider_id == provider_id)
            if provider_pool:
                q = q.filter(TokenLedgerEntry.provider_pool == provider_pool)
            if day:
                import datetime
                start = datetime.datetime.strptime(day, "%Y-%m-%d").timestamp()
                end = start + 86400
                q = q.filter(TokenLedgerEntry.timestamp >= start, TokenLedgerEntry.timestamp < end)
            if month:
                import datetime
                start = datetime.datetime.strptime(month + "-01", "%Y-%m-%d").timestamp()
                # End = start of next month
                dt = datetime.datetime.strptime(month + "-01", "%Y-%m-%d")
                if dt.month == 12:
                    next_month = dt.replace(year=dt.year + 1, month=1)
                else:
                    next_month = dt.replace(month=dt.month + 1)
                end = next_month.timestamp()
                q = q.filter(TokenLedgerEntry.timestamp >= start, TokenLedgerEntry.timestamp < end)

            rows = q.all()
            if not rows:
                return {"count": 0}

            return {
                "count": len(rows),
                "input_tokens": sum(r.input_tokens for r in rows),
                "output_tokens": sum(r.output_tokens for r in rows),
                "cached_tokens": sum(r.cached_tokens for r in rows),
                "actual_tokens": sum(r.actual_tokens for r in rows),
                "compression_savings": sum(r.compression_savings for r in rows),
                "avg_latency_ms": sum(r.latency_ms for r in rows) / len(rows),
                "errors": sum(1 for r in rows if r.status != "ok"),
                "models_used": list({r.model_id for r in rows if r.model_id}),
                "providers_used": list({r.provider_id for r in rows if r.provider_id}),
                "pools_used": list({r.provider_pool for r in rows if r.provider_pool}),
            }


# Module-level singleton
_default_ledger: Optional[TokenLedger] = None


def get_ledger() -> TokenLedger:
    global _default_ledger
    if _default_ledger is None:
        _default_ledger = TokenLedger()
    return _default_ledger
