"""Obsidian Vault Integration Service for Aurex.

Provides bidirectional communication, CRUD, graph topology, search, and desktop
linking for the user's Obsidian vault.
"""

import os
import re
import json
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple

logger = logging.getLogger(__name__)

DEFAULT_VAULT_PATH = os.path.expanduser("~/Vault")

# Celestial Universe Palette matching Obsidian's graph view
CATEGORY_COLORS = {
    "moc": {"hex": "#e9d5ff", "rgb": 15324671, "label": "Galactic Core"},
    "module": {"hex": "#38bdf8", "rgb": 3718648, "label": "Planetary Modules"},
    "concept": {"hex": "#22d3ee", "rgb": 2282478, "label": "Concepts"},
    "theorem": {"hex": "#fde047", "rgb": 16638023, "label": "Theorems"},
    "definition": {"hex": "#6ee7b7", "rgb": 7268279, "label": "Definitions"},
    "mathematician": {"hex": "#c084fc", "rgb": 12616956, "label": "Mathematicians"},
    "bridge": {"hex": "#f472b6", "rgb": 16020150, "label": "Cross-Bridges"},
    "example": {"hex": "#fda4af", "rgb": 16622767, "label": "Worked Examples"},
    "flashcard": {"hex": "#fed7aa", "rgb": 16701354, "label": "Flashcards"},
    "formula": {"hex": "#ffffff", "rgb": 16777215, "label": "Formulas"},
    "study-day": {"hex": "#93c5fd", "rgb": 9684477, "label": "Study Arc"},
    "exam": {"hex": "#f87171", "rgb": 16281969, "label": "Exam Milestones"},
    "canvas": {"hex": "#f1f5f9", "rgb": 15857145, "label": "Canvas Mindmap"},
    "default": {"hex": "#94a3b8", "rgb": 9741240, "label": "Notes"},
    "ghost": {"hex": "#e2e8f0", "rgb": 14869232, "label": "Uncreated Forward Link"}
}


class ObsidianVaultService:
    def __init__(self, vault_path: Optional[str] = None):
        self.vault_path = Path(vault_path or DEFAULT_VAULT_PATH).resolve()
        self.category_colors = dict(CATEGORY_COLORS)
        
    def _get_dynamic_color(self, category: str) -> dict:
        if category in self.category_colors:
            return self.category_colors[category]
        
        # Generate a deterministic pseudo-random pastel color based on the category string
        import hashlib
        h = int(hashlib.md5(category.encode()).hexdigest(), 16)
        r = (h & 0xFF) % 128 + 127
        g = ((h >> 8) & 0xFF) % 128 + 127
        b = ((h >> 16) & 0xFF) % 128 + 127
        
        rgb_val = (r << 16) + (g << 8) + b
        hex_val = f"#{r:02x}{g:02x}{b:02x}"
        
        self.category_colors[category] = {
            "hex": hex_val,
            "rgb": rgb_val,
            "label": category.title()
        }
        return self.category_colors[category]


    def _is_valid_path(self, p: Path) -> bool:
        """Check if path is not in a hidden directory like .obsidian or .git."""
        try:
            rel = p.relative_to(self.vault_path)
            return not any(part.startswith('.') for part in rel.parts)
        except ValueError:
            return False

    def get_status(self) -> Dict[str, Any]:
        """Return vault status, note count, link count, and health."""
        if not self.vault_path.exists():
            return {
                "exists": False,
                "path": str(self.vault_path),
                "error": "Vault path does not exist"
            }

        notes = [p for p in self.vault_path.glob("**/*.md") if self._is_valid_path(p)]
        canvas_files = [p for p in self.vault_path.glob("**/*.canvas") if self._is_valid_path(p)]
        folders = [p.name for p in self.vault_path.iterdir() if p.is_dir() and not p.name.startswith(".")]

        # Count total links
        total_links = 0
        for n in notes:
            try:
                text = n.read_text(encoding="utf-8")
                total_links += len(re.findall(r"\[\[(.*?)\]\]", text))
            except Exception:
                pass

        return {
            "exists": True,
            "path": str(self.vault_path),
            "total_notes": len(notes),
            "total_canvas": len(canvas_files),
            "total_links": total_links,
            "folders": sorted(folders),
            "app_installed": Path(os.path.expanduser("~/.local/bin/obsidian")).exists()
        }

    def _parse_frontmatter(self, text: str) -> Tuple[Dict[str, Any], str]:
        """Extract YAML frontmatter and body from markdown text."""
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
        if not m:
            return {}, text

        fm_text = m.group(1)
        body = m.group(2)
        meta = {}
        current_list_key = None

        for line in fm_text.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            if line_str.startswith("- ") and current_list_key:
                val = line_str[2:].strip().strip('"').strip("'")
                meta.setdefault(current_list_key, []).append(val)
            elif ":" in line_str:
                k, v = line_str.split(":", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if not v:
                    current_list_key = k
                    meta[k] = []
                else:
                    current_list_key = None
                    meta[k] = v

        return meta, body

    def _detect_category(self, rel_path: str, tags: List[str], text: str) -> str:
        """Categorize a note dynamically based on folders or tags."""
        if rel_path.endswith(".canvas"):
            return "canvas"
        
        folder = rel_path.split("/")[0] if "/" in rel_path else ""
        if folder and not folder.startswith("."):
            return folder.lower()
            
        if tags and len(tags) > 0:
            t = tags[0].lower()
            if t.startswith("#"):
                t = t[1:]
            return t
            
        return "uncategorized"
    def list_notes(self, folder: Optional[str] = None, tag: Optional[str] = None) -> List[Dict[str, Any]]:
        """List notes with title, folder, tags, category, and outgoing link count."""
        results = []
        pattern = f"{folder}/**/*.md" if folder else "**/*.md"

        for p in sorted([p for p in self.vault_path.glob(pattern) if self._is_valid_path(p)]):
            if not self._is_valid_path(p):
                continue
            rel_path = str(p.relative_to(self.vault_path))
            try:
                content = p.read_text(encoding="utf-8")
                fm, body = self._parse_frontmatter(content)
                tags = fm.get("tags", [])
                if isinstance(tags, str):
                    tags = [tags]

                # Filter by tag if requested
                if tag and tag.lower() not in [t.lower() for t in tags]:
                    continue

                title = fm.get("title")
                if not title:
                    # Look for first # header
                    h = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
                    title = h.group(1).strip() if h else p.stem

                links = re.findall(r"\[\[(.*?)\]\]", content)
                clean_links = [l.split("|")[0].split("#")[0] for l in links if "],[" not in l and not re.match(r'^[0-9\s,\.\-]+$', l)]
                category = self._detect_category(rel_path, tags, content)

                results.append({
                    "path": rel_path,
                    "stem": p.stem,
                    "title": title,
                    "folder": p.parent.name if p.parent != self.vault_path else "Root",
                    "tags": tags,
                    "category": category,
                    "color": self._get_dynamic_color(category)["hex"],
                    "link_count": len(clean_links),
                    "size": p.stat().st_size,
                    "modified": p.stat().st_mtime
                })
            except Exception as e:
                logger.debug(f"Failed to parse {rel_path}: {e}")

        return results

    def read_note(self, rel_path: str) -> Optional[Dict[str, Any]]:
        """Read a note and return its content, frontmatter, backlinks, and forward links."""
        # Clean extension
        if not rel_path.endswith(".md") and not rel_path.endswith(".canvas"):
            rel_path += ".md"

        target_file = (self.vault_path / rel_path).resolve()
        if not target_file.exists() or not str(target_file).startswith(str(self.vault_path)):
            return None

        content = target_file.read_text(encoding="utf-8")
        fm, body = self._parse_frontmatter(content)
        tags = fm.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]

        # Extract outgoing links
        raw_links = re.findall(r"\[\[(.*?)\]\]", content)
        outgoing = []
        for l in raw_links:
            clean = l.split("|")[0].split("#")[0]
            alias = l.split("|")[1] if "|" in l else clean
            outgoing.append({"target": clean, "alias": alias})

        # Calculate incoming backlinks across the vault
        stem = target_file.stem
        backlinks = []
        for p in [p for p in self.vault_path.glob("**/*.md") if self._is_valid_path(p)]:
            if p == target_file or p.name.startswith("."):
                continue
            try:
                p_text = p.read_text(encoding="utf-8")
                if f"[[{stem}]]" in p_text or f"[[{rel_path.replace('.md', '')}]]" in p_text or f"[[{stem}|" in p_text:
                    p_rel = str(p.relative_to(self.vault_path))
                    backlinks.append({"path": p_rel, "title": p.stem})
            except Exception:
                pass

        category = self._detect_category(rel_path, tags, content)

        return {
            "path": rel_path,
            "stem": target_file.stem,
            "title": fm.get("title") or target_file.stem,
            "content": content,
            "body": body,
            "frontmatter": fm,
            "tags": tags,
            "category": category,
            "color": self._get_dynamic_color(category)["hex"],
            "outgoing_links": outgoing,
            "backlinks": backlinks,
            "modified": target_file.stat().st_mtime
        }

    def save_note(self, rel_path: str, content: str) -> Dict[str, Any]:
        """Create or update a note in the vault."""
        if not rel_path.endswith(".md"):
            rel_path += ".md"

        target_file = (self.vault_path / rel_path).resolve()
        if not str(target_file).startswith(str(self.vault_path)):
            raise ValueError("Target path must be inside the vault directory")

        target_file.parent.mkdir(parents=True, exist_ok=True)
        is_new = not target_file.exists()
        target_file.write_text(content, encoding="utf-8")

        # Refresh Aurex RAG in background
        self._refresh_aurex_rag()

        return {
            "success": True,
            "path": rel_path,
            "created": is_new,
            "bytes_written": len(content)
        }

    def delete_note(self, rel_path: str) -> Dict[str, Any]:
        """Delete a note from the vault."""
        if not rel_path.endswith(".md"):
            rel_path += ".md"

        target_file = (self.vault_path / rel_path).resolve()
        if not target_file.exists() or not str(target_file).startswith(str(self.vault_path)):
            return {"success": False, "error": "Note does not exist"}

        target_file.unlink()
        self._refresh_aurex_rag()
        return {"success": True, "path": rel_path}

    def search_notes(self, query: str) -> List[Dict[str, Any]]:
        """Search notes by title or content."""
        query_lower = query.lower()
        results = []

        for p in [p for p in self.vault_path.glob("**/*.md") if self._is_valid_path(p)]:
            if not self._is_valid_path(p):
                continue
            try:
                text = p.read_text(encoding="utf-8")
                rel_path = str(p.relative_to(self.vault_path))
                title = p.stem

                # Check title match or content match
                score = 0
                snippet = ""
                if query_lower in title.lower():
                    score += 10
                if query_lower in text.lower():
                    score += 5
                    idx = text.lower().find(query_lower)
                    start = max(0, idx - 60)
                    end = min(len(text), idx + 140)
                    snippet = "..." + text[start:end].replace("\n", " ") + "..."

                if score > 0:
                    fm, _ = self._parse_frontmatter(text)
                    tags = fm.get("tags", [])
                    if isinstance(tags, str):
                        tags = [tags]
                    cat = self._detect_category(rel_path, tags, text)
                    results.append({
                        "path": rel_path,
                        "title": fm.get("title") or title,
                        "snippet": snippet,
                        "score": score,
                        "category": cat,
                        "color": self._get_dynamic_color(cat)["hex"],
                        "tags": tags
                    })
            except Exception:
                pass

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:30]

    def get_graph_data(self) -> Dict[str, Any]:
        """Build graph nodes and links for web-based interactive visualization."""
        nodes = []
        links = []
        node_map = {}

        # 1. Collect all markdown notes
        for p in [p for p in self.vault_path.glob("**/*.md") if self._is_valid_path(p)]:
            if not self._is_valid_path(p):
                continue
            rel_path = str(p.relative_to(self.vault_path))
            try:
                text = p.read_text(encoding="utf-8")
                fm, body = self._parse_frontmatter(text)
                tags = fm.get("tags", [])
                if isinstance(tags, str):
                    tags = [tags]

                cat = self._detect_category(rel_path, tags, text)
                color_info = self._get_dynamic_color(cat)

                node_id = rel_path.replace(".md", "")
                stem = p.stem
                title = fm.get("title") or stem

                node_obj = {
                    "id": node_id,
                    "stem": stem,
                    "title": title,
                    "path": rel_path,
                    "category": cat,
                    "color": color_info["hex"],
                    "color_rgb": color_info["rgb"],
                    "category_label": color_info["label"],
                    "degree": 0,
                    "tags": tags
                }
                nodes.append(node_obj)
                node_map[node_id] = node_obj
                node_map[stem] = node_obj
            except Exception:
                pass

        # 2. Collect canvas file
        for c in [p for p in self.vault_path.glob("**/*.canvas") if self._is_valid_path(p)]:
            rel_path = str(c.relative_to(self.vault_path))
            stem = c.stem
            node_id = rel_path
            node_obj = {
                "id": node_id,
                "stem": stem,
                "title": stem,
                "path": rel_path,
                "category": "canvas",
                "color": self._get_dynamic_color("canvas")["hex"],
                "color_rgb": self._get_dynamic_color("canvas")["rgb"],
                "category_label": "Canvas Mindmap",
                "degree": 0,
                "tags": ["canvas"]
            }
            nodes.append(node_obj)
            node_map[node_id] = node_obj
            node_map[stem] = node_obj

        # 3. Build edges
        seen_edges = set()
        for p in [p for p in self.vault_path.glob("**/*.md") if self._is_valid_path(p)]:
            if not self._is_valid_path(p):
                continue
            src_id = str(p.relative_to(self.vault_path)).replace(".md", "")
            try:
                text = p.read_text(encoding="utf-8")
                raw_links = re.findall(r"\[\[(.*?)\]\]", text)
                for l in raw_links:
                    # Ignore matrices/arrays
                    if "],[" in l or re.match(r'^[0-9\s,\.\-]+$', l):
                        continue
                    clean = l.split("|")[0].split("#")[0]
                    if not clean:
                        continue
                    
                    target_node = node_map.get(clean)
                    
                    # Create ghost node if it doesn't exist (like Obsidian forward links)
                    if not target_node:
                        ghost_id = clean
                        target_node = {
                            "id": ghost_id,
                            "stem": clean,
                            "title": clean,
                            "path": clean + ".md",
                            "category": "ghost",
                            "color": "#e2e8f0", # Light gray for ghost nodes
                            "color_rgb": 14869232,
                            "category_label": "Uncreated Forward Link",
                            "degree": 0,
                            "tags": ["ghost"]
                        }
                        nodes.append(target_node)
                        node_map[clean] = target_node
                        node_map[ghost_id] = target_node

                    tgt_id = target_node["id"]
                    edge_key = f"{src_id}-->{tgt_id}"
                    if edge_key not in seen_edges and src_id != tgt_id:
                        seen_edges.add(edge_key)
                        links.append({
                            "source": src_id,
                            "target": tgt_id
                        })
                        if src_id in node_map:
                            node_map[src_id]["degree"] += 1
                        target_node["degree"] += 1
            except Exception:
                pass

        return {
            "nodes": nodes,
            "links": links,
            "total_nodes": len(nodes),
            "total_links": len(links),
            "categories": self.category_colors
        }

    def open_in_app(self, rel_path: Optional[str] = None) -> Dict[str, Any]:
        """Trigger opening in native Obsidian desktop app via URI."""
        import urllib.parse
        vault_name = self.vault_path.name
        
        if rel_path:
            clean_file = rel_path.replace(".md", "")
            uri = f"obsidian://open?vault={urllib.parse.quote(vault_name)}&file={urllib.parse.quote(clean_file)}"
        else:
            uri = f"obsidian://open?vault={urllib.parse.quote(vault_name)}"

        try:
            # Use xdg-open on Linux
            subprocess.Popen(["xdg-open", uri], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"success": True, "uri": uri, "opened": True}
        except Exception as e:
            logger.error(f"Failed to open URI: {e}")
            return {"success": False, "error": str(e), "uri": uri}

    def _refresh_aurex_rag(self):
        """Asynchronously trigger Aurex RAG re-index so personal docs stay in sync."""
        try:
            from src.personal_docs import PersonalDocsManager
            from src.constants import PERSONAL_DIR
            pdm = PersonalDocsManager(personal_dir=PERSONAL_DIR)
            pdm.refresh_index()
        except Exception as e:
            logger.debug(f"Background RAG refresh note: {e}")


# Singleton instance
_vault_service = None

def get_obsidian_service() -> ObsidianVaultService:
    global _vault_service
    if _vault_service is None:
        _vault_service = ObsidianVaultService()
    return _vault_service
