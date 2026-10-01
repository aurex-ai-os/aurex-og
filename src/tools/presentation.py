import json
import logging
import os
import re
from typing import Dict, Optional
from fpdf import FPDF
import markdown2
from pptx import Presentation
from pptx.util import Inches, Pt
from src.tools._common import _parse_tool_args

logger = logging.getLogger(__name__)

async def do_export_document(content: str, owner: Optional[str] = None) -> Dict:
    """Export markdown content to PDF or PPTX."""
    try:
        args = _parse_tool_args(content)
    except ValueError:
        return {"error": "Invalid JSON arguments", "exit_code": 1}

    format_type = args.get("format", "pdf").lower()
    title = args.get("title", "Export")
    md_content = args.get("content", "")
    
    if not md_content:
        return {"error": "Missing 'content'", "exit_code": 1}

    os.makedirs("exports", exist_ok=True)
    filename = f"exports/{title.replace(' ', '_')}.{format_type}"

    try:
        if format_type == "pdf":
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("helvetica", size=12)
            
            # Simple conversion: strip basic markdown for fpdf text
            lines = md_content.split('\n')
            for line in lines:
                if line.startswith('#'):
                    pdf.set_font("helvetica", style="B", size=16)
                    pdf.multi_cell(0, 10, text=line.replace('#', '').strip())
                    pdf.set_font("helvetica", size=12)
                elif line.startswith('-') or line.startswith('*'):
                    pdf.multi_cell(0, 8, text=f"   • {line[1:].strip()}")
                else:
                    pdf.multi_cell(0, 8, text=line)
            pdf.output(filename)
            
        elif format_type == "pptx":
            prs = Presentation()
            
            # Split content by H1/H2 for slides
            slides = re.split(r'\n# ', '\n' + md_content)
            for slide_content in slides:
                if not slide_content.strip(): continue
                lines = slide_content.strip().split('\n')
                slide_title = lines[0].replace('#', '').strip()
                slide_body = '\n'.join(lines[1:]).strip()
                
                # Add slide
                slide_layout = prs.slide_layouts[1] # Title and Content
                slide = prs.slides.add_slide(slide_layout)
                
                title_shape = slide.shapes.title
                title_shape.text = slide_title
                
                if slide_body:
                    body_shape = slide.placeholders[1]
                    tf = body_shape.text_frame
                    tf.text = slide_body
            
            prs.save(filename)
            
        else:
            return {"error": "Format must be pdf or pptx", "exit_code": 1}
            
        # Also save to Obsidian if available
        from src.tools.obsidian import do_manage_obsidian
        await do_manage_obsidian(json.dumps({
            "action": "create",
            "path": f"Exports/{title}.md",
            "content": f"Exported as {format_type.upper()}.\n\n" + md_content
        }), owner=owner)

        return {
            "success": True,
            "message": f"Successfully generated {filename} on disk, and saved backup to Obsidian Exports/{title}.md"
        }
    except Exception as e:
        logger.error(f"Export error: {e}")
        return {"error": str(e), "exit_code": 1}

