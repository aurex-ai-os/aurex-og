import json
import logging
from typing import Dict, Optional
from datetime import datetime, timedelta

from src.tools._common import _parse_tool_args
from src.tools.calendar import do_manage_calendar
from src.tools.obsidian import do_manage_obsidian

logger = logging.getLogger(__name__)

async def do_student_study_planner(content: str, owner: Optional[str] = None) -> Dict:
    """Generate a super powerful study plan combining Calendar spaced-repetition and Obsidian tracking."""
    try:
        args = _parse_tool_args(content)
    except ValueError:
        return {"error": "Invalid JSON arguments", "exit_code": 1}

    subject = args.get("subject", "Study Plan")
    topics = args.get("topics", [])
    exam_date_str = args.get("exam_date")
    
    if not topics or not exam_date_str:
        return {"error": "Missing 'topics' list or 'exam_date' (YYYY-MM-DD)", "exit_code": 1}

    try:
        exam_date = datetime.strptime(exam_date_str[:10], "%Y-%m-%d")
    except Exception as e:
        return {"error": f"Invalid exam_date format. Use YYYY-MM-DD. {e}", "exit_code": 1}

    now = datetime.now()
    days_until_exam = (exam_date - now).days
    
    if days_until_exam <= 0:
        return {"error": "Exam date must be in the future.", "exit_code": 1}

    # Generate Obsidian Dashboard with Graph connections
    md_content = f"---\ntags: [study-plan, exams, student-intelligence]\n---\n# 🎓 Master Study Plan: [[{subject}]]\n\n**Exam Date:** {exam_date_str[:10]}\n**Days Remaining:** {days_until_exam}\n\n## 📚 Topics to Master\n"

    for t in topics:
        md_content += f"- [ ] {t}\n"
    md_content += "\n## 🧠 Spaced Repetition Schedule\n"
    md_content += "| Topic | Day 1 (Learn) | Day 3 (Review) | Day 7 (Recall) | Final Review |\n"
    md_content += "|---|---|---|---|---|\n"

    # Distribute topics across the days
    events_created = []
    
    for i, topic in enumerate(topics):
        # Learn day
        learn_date = now + timedelta(days=(i % max(1, days_until_exam - 2)))
        # Spaced repetition logic
        review1 = learn_date + timedelta(days=2)
        review2 = learn_date + timedelta(days=6)
        final_review = exam_date - timedelta(days=1)
        
        md_content += f"| **{topic}** | {learn_date.strftime('%b %d')} | {review1.strftime('%b %d') if review1 < exam_date else '-'} | {review2.strftime('%b %d') if review2 < exam_date else '-'} | {final_review.strftime('%b %d')} |\n"

        # Create Learn Event
        ev = {
            "action": "create_event",
            "summary": f"📚 Learn: {topic}",
            "description": f"Initial learning phase for {topic}. Master the core concepts.",
            "dtstart": learn_date.strftime("%Y-%m-%dT09:00:00"),
            "dtend": learn_date.strftime("%Y-%m-%dT11:00:00"),
            "event_type": "study"
        }
        await do_manage_calendar(json.dumps(ev), owner=owner)
        events_created.append(ev["summary"])

        # Create Review Event if it fits before exam
        if review1 < exam_date:
            ev2 = {
                "action": "create_event",
                "summary": f"🧠 Review: {topic}",
                "description": f"Spaced repetition review for {topic}. Try active recall.",
                "dtstart": review1.strftime("%Y-%m-%dT16:00:00"),
                "dtend": review1.strftime("%Y-%m-%dT17:00:00"),
                "event_type": "study"
            }
            await do_manage_calendar(json.dumps(ev2), owner=owner)

    # Obsidian write
    obs_req = {
        "action": "create",
        "path": f"Student Intelligence/Study Plan - {subject}.md",
        "content": md_content
    }
    await do_manage_obsidian(json.dumps(obs_req), owner=owner)

    return {
        "success": True,
        "message": f"Successfully generated a Super Powerful Study Plan for {subject}! Created Master Dashboard in Obsidian and scheduled {len(events_created) * 2} spaced-repetition calendar blocks."
    }

