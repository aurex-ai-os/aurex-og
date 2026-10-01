import logging
from typing import List, Dict, Any
from .models import Syllabus, CourseUnit, Topic, Concept

logger = logging.getLogger(__name__)

class SyllabusIngestionPipeline:
    def __init__(self, session):
        self.session = session
        logger.info("Initialized SyllabusIngestionPipeline")

    def ingest(self, course_id: int, extracted_text: str, metadata: Dict[str, Any]) -> Syllabus:
        """
        Takes extracted text and structures it into Phase 1 models.
        """
        logger.info(f"Ingesting syllabus for course {course_id}")
        
        # Create Syllabus record
        syllabus = Syllabus(course_id=course_id, raw_text=extracted_text)
        self.session.add(syllabus)
        self.session.commit()
        
        source_file = metadata.get("source_file", "unknown")
        
        unit = CourseUnit(syllabus_id=syllabus.id, title="Parsed Unit 1", order=1)
        self.session.add(unit)
        self.session.commit()
        
        topic = Topic(unit_id=unit.id, title="Parsed Topic 1", weight=0.5, estimated_learning_hours=2.0)
        self.session.add(topic)
        self.session.commit()
        
        concept = Concept(
            topic_id=topic.id,
            name="Parsed Concept 1",
            source_file=source_file,
            page_num=metadata.get("page_num", 1)
        )
        self.session.add(concept)
        self.session.commit()
        
        return syllabus
