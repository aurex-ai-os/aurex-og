from fastapi import APIRouter
from typing import Dict, Any, List

student_router = APIRouter(prefix="/student", tags=["student"])

@student_router.get('/dashboard/today')
def get_today_tasks() -> Dict[str, List[str]]:
    return {"tasks": ["Review Calculus", "Complete History Reading"]}

@student_router.get('/dashboard/progress')
def get_progress() -> Dict[str, Dict[str, int]]:
    return {"progress": {"Calculus": 75, "History": 40}}

@student_router.get('/dashboard/courses')
def get_courses() -> Dict[str, List[str]]:
    return {"courses": ["Calculus", "History"]}

@student_router.get('/dashboard/knowledge')
def get_knowledge_map() -> Dict[str, Any]:
    return {"nodes": ["Derivatives", "Integrals"], "edges": []}

@student_router.get('/dashboard/exam-countdown')
def get_exam_countdown() -> Dict[str, List[Dict[str, Any]]]:
    return {"exams": [{"course": "Calculus", "days_left": 14}]}
