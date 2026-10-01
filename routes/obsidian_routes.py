"""Obsidian Vault REST API routes for Aurex."""

import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Body, Depends
from src.auth_helpers import require_user
from src.obsidian_service import get_obsidian_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/obsidian", tags=["obsidian"])


@router.get("/status")
async def get_status(user: Any = Depends(require_user)):
    """Return vault status, note count, link count, and health."""
    svc = get_obsidian_service()
    return svc.get_status()


@router.get("/notes")
async def list_notes(
    folder: Optional[str] = Query(None, description="Filter by subfolder"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    user: Any = Depends(require_user)
):
    """List notes with title, tags, category, and outgoing link count."""
    svc = get_obsidian_service()
    return {"notes": svc.list_notes(folder=folder, tag=tag)}


@router.get("/graph")
async def get_graph(user: Any = Depends(require_user)):
    """Get graph topology (nodes, links, degree, categories) for frontend rendering."""
    svc = get_obsidian_service()
    return svc.get_graph_data()


@router.get("/search")
async def search_notes(
    q: str = Query(..., min_length=1, description="Search term"),
    user: Any = Depends(require_user)
):
    """Search notes across titles and content."""
    svc = get_obsidian_service()
    return {"results": svc.search_notes(q)}


@router.get("/notes/{path:path}")
async def get_note(path: str, user: Any = Depends(require_user)):
    """Get full content, parsed frontmatter, outgoing links, and backlinks of a note."""
    svc = get_obsidian_service()
    note = svc.read_note(path)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.post("/notes")
async def save_note(
    payload: Dict[str, Any] = Body(...),
    user: Any = Depends(require_user)
):
    """Create or update a note in the vault."""
    path = payload.get("path")
    content = payload.get("content")
    if not path or content is None:
        raise HTTPException(status_code=400, detail="Missing path or content in payload")

    svc = get_obsidian_service()
    try:
        res = svc.save_note(path, content)
        return res
    except Exception as e:
        logger.error(f"Error saving note {path}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/notes/{path:path}")
async def delete_note(path: str, user: Any = Depends(require_user)):
    """Delete a note from the vault."""
    svc = get_obsidian_service()
    res = svc.delete_note(path)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Delete failed"))
    return res


@router.post("/open")
async def open_in_obsidian(
    payload: Dict[str, Any] = Body(...),
    user: Any = Depends(require_user)
):
    """Trigger opening note or vault in native desktop Obsidian app."""
    path = payload.get("path")
    svc = get_obsidian_service()
    res = svc.open_in_app(path)
    return res


@router.post("/sync")
async def sync_vault_to_rag(user: Any = Depends(require_user)):
    """Force re-index vault notes into Aurex RAG."""
    svc = get_obsidian_service()
    try:
        from src.personal_docs import PersonalDocsManager
        from src.constants import PERSONAL_DIR
        pdm = PersonalDocsManager(personal_dir=PERSONAL_DIR)
        pdm.refresh_index()
        stats = pdm.get_stats()
        return {"success": True, "stats": stats}
    except Exception as e:
        logger.error(f"Failed to sync vault to RAG: {e}")
        return {"success": False, "error": str(e)}


def setup_obsidian_routes() -> APIRouter:
    return router
