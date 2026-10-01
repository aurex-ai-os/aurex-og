import logging
from typing import List, Dict, Any
from .models import Syllabus, Concept, Topic

logger = logging.getLogger(__name__)

class SyllabusIntelligenceEngine:
    def __init__(self, session):
        self.session = session
        logger.info("Initialized SyllabusIntelligenceEngine")

    def analyze(self, syllabus_id: int) -> Dict[str, Any]:
        """
        Analyzes the ingested syllabus to identify relationships, high-weight topics, etc.
        """
        logger.info(f"Analyzing syllabus {syllabus_id}")
        
        syllabus = self.session.query(Syllabus).filter_by(id=syllabus_id).first()
        if not syllabus:
            return {}

        # 1. Prerequisite relationships and concept dependencies
        concepts = self.session.query(Concept).join(Topic).join(Topic.unit).filter_by(syllabus_id=syllabus.id).all()
        concept_deps = {c.id: c.prerequisite_id for c in concepts if c.prerequisite_id}

        # 2. High-weight topics
        topics = self.session.query(Topic).join(Topic.unit).filter_by(syllabus_id=syllabus.id).order_by(Topic.weight.desc()).all()
        high_weight = [t.title for t in topics if t.weight and t.weight > 0.2]

        # 3. Estimated learning time
        total_time = sum(t.estimated_learning_hours for t in topics if t.estimated_learning_hours)

        return {
            "concept_dependencies": concept_deps,
            "high_weight_topics": high_weight,
            "total_estimated_learning_hours": total_time
        }
