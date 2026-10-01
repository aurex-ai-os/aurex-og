"""Obsidian-domain tool implementations for Aurex AI Agent."""

import json
import logging
from typing import Dict, Optional, Any
from src.tools._common import _parse_tool_args
from src.obsidian_service import get_obsidian_service

logger = logging.getLogger(__name__)


async def do_manage_obsidian(content: str, owner: Optional[str] = None) -> Dict[str, Any]:
    """Handle manage_obsidian tool calls for AI interaction with Obsidian Vault."""
    try:
        args = _parse_tool_args(content)
    except ValueError:
        return {"error": "Invalid JSON arguments", "exit_code": 1}

    raw_action = (args.get("action") or "").strip().lower()
    action_aliases = {
        "list_notes": "list",
        "read_note": "read",
        "get_note": "read",
        "create_note": "create",
        "add_note": "create",
        "new_note": "create",
        "write_note": "create",
        "save_note": "create",
        "update_note": "update",
        "append_note": "append",
        "search_notes": "search",
        "query": "search",
        "status": "graph_stats",
        "vault_status": "graph_stats",
        "stats": "graph_stats",
        "graph": "graph_stats",
        "connections": "get_links",
        "backlinks": "get_links",
        "open": "open_in_app",
        "launch": "open_in_app"
    }
    action = action_aliases.get(raw_action, raw_action)
    svc = get_obsidian_service()

    try:
        if action == "list":
            folder = args.get("folder")
            tag = args.get("tag")
            notes = svc.list_notes(folder=folder, tag=tag)
            return {
                "success": True,
                "action": "list",
                "count": len(notes),
                "notes": [
                    {
                        "path": n["path"],
                        "title": n["title"],
                        "folder": n["folder"],
                        "category": n["category"],
                        "tags": n["tags"],
                        "links": n["link_count"]
                    }
                    for n in notes
                ]
            }

        elif action == "read":
            path = args.get("path") or args.get("file") or args.get("title")
            if not path:
                return {"error": "Missing 'path' or 'title' argument", "exit_code": 1}

            # If user passed just a title, search for matching note
            note = svc.read_note(path)
            if not note:
                # Try finding by stem
                for n in svc.list_notes():
                    if n["stem"].lower() == path.lower() or n["title"].lower() == path.lower():
                        note = svc.read_note(n["path"])
                        break

            if not note:
                return {"error": f"Note '{path}' not found in Obsidian vault", "exit_code": 1}

            return {
                "success": True,
                "action": "read",
                "path": note["path"],
                "title": note["title"],
                "category": note["category"],
                "tags": note["tags"],
                "content": note["content"],
                "outgoing_links": [l["target"] for l in note["outgoing_links"]],
                "backlinks": [b["title"] for b in note["backlinks"]]
            }

        elif action in ("create", "update", "save"):
            path = args.get("path") or args.get("file") or args.get("title")
            text = args.get("content") or args.get("text")
            if not path or text is None:
                return {"error": "Missing 'path' and 'content' arguments", "exit_code": 1}

            # If path lacks folder, put in Concepts/ or root
            if "/" not in path and not path.endswith(".md"):
                folder = args.get("folder", "")
                path = f"{folder}/{path}.md" if folder else f"{path}.md"

            res = svc.save_note(path, text)
            return {
                "success": True,
                "action": action,
                "path": res["path"],
                "created": res["created"],
                "message": f"Successfully {'created' if res['created'] else 'updated'} '{res['path']}' in Obsidian Vault"
            }

        elif action == "append":
            path = args.get("path") or args.get("file")
            text = args.get("content") or args.get("text") or ""
            if not path:
                return {"error": "Missing 'path' argument", "exit_code": 1}

            existing = svc.read_note(path)
            if not existing:
                return {"error": f"Note '{path}' does not exist to append to", "exit_code": 1}

            new_content = existing["content"].rstrip() + "\n\n" + text
            res = svc.save_note(existing["path"], new_content)
            return {
                "success": True,
                "action": "append",
                "path": res["path"],
                "message": f"Successfully appended content to '{res['path']}'"
            }

        elif action == "search":
            query = args.get("query") or args.get("q") or ""
            if not query:
                return {"error": "Missing 'query' argument", "exit_code": 1}
            results = svc.search_notes(query)
            return {
                "success": True,
                "action": "search",
                "query": query,
                "count": len(results),
                "results": results
            }

        elif action == "graph_stats":
            status = svc.get_status()
            graph = svc.get_graph_data()
            # Top connected hubs
            sorted_nodes = sorted(graph["nodes"], key=lambda x: x["degree"], reverse=True)
            top_hubs = [{"title": n["title"], "degree": n["degree"], "category": n["category"]} for n in sorted_nodes[:10]]
            return {
                "success": True,
                "action": "graph_stats",
                "vault_path": status["path"],
                "total_notes": status["total_notes"],
                "total_links": status["total_links"],
                "folders": status["folders"],
                "top_connected_hubs": top_hubs
            }

        elif action == "get_links":
            path = args.get("path") or args.get("title")
            if not path:
                return {"error": "Missing 'path' or 'title' argument", "exit_code": 1}
            note = svc.read_note(path)
            if not note:
                return {"error": f"Note '{path}' not found", "exit_code": 1}
            return {
                "success": True,
                "action": "get_links",
                "path": note["path"],
                "title": note["title"],
                "outgoing_links": note["outgoing_links"],
                "backlinks": note["backlinks"]
            }

        elif action == "open_in_app":
            path = args.get("path") or args.get("file")
            res = svc.open_in_app(path)
            return {
                "success": res.get("success", False),
                "action": "open_in_app",
                "uri": res.get("uri"),
                "message": f"Opened '{path or 'Vault'}' in Obsidian desktop application"
            }

        else:
            return {
                "error": f"Unknown action '{raw_action}'. Supported: list, read, create, update, append, search, graph_stats, get_links, open_in_app",
                "exit_code": 1
            }

    except Exception as e:
        logger.error(f"manage_obsidian execution error: {e}", exc_info=True)
        return {"error": str(e), "exit_code": 1}
