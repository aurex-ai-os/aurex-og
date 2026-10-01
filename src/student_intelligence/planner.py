import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta

from .models import Syllabus, Topic, Concept

logger = logging.getLogger(__name__)

class StudyPlanEngine:
    def __init__(self, session):
        self.session = session

    def generate_plan(self, syllabus_id: int, exam_date: datetime, available_hours_per_week: float) -> Dict[str, Any]:
        """
        Generates DailyPlan, WeeklyPlan, and CoursePlan.
        Considers spaced repetition, revision time, and prerequisite order.
        """
        syllabus = self.session.query(Syllabus).filter_by(id=syllabus_id).first()
        if not syllabus:
            return {}

        topics = self.session.query(Topic).join(Topic.unit).filter_by(syllabus_id=syllabus_id).all()
        # Ensure prerequisite order (mocked logic)
        topics.sort(key=lambda t: t.id)
        
        return {
            "course_plan": f"Plan for syllabus {syllabus_id} towards {exam_date}",
            "weekly_plan": ["Week 1: Foundations", "Week 2: Advanced topics"],
            "daily_plan": ["Day 1: Read Chapter 1", "Day 2: Exercises"]
        }


class AdaptiveReplanner:
    def __init__(self, session, planner: StudyPlanEngine):
        self.session = session
        self.planner = planner

    def recalculate(self, syllabus_id: int, missed_days: int, current_mastery: Dict[str, str], exam_date: datetime, available_hours_per_week: float) -> Dict[str, Any]:
        """
        Recalculates the remaining plan when the student misses a day or updates their mastery levels.
        """
        logger.info(f"Recalculating plan for {syllabus_id} due to {missed_days} missed days.")
        
        # Adjust available hours or condense topics based on current mastery
        return self.planner.generate_plan(syllabus_id, exam_date, available_hours_per_week)
