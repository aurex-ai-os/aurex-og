import logging
from typing import Dict, List
from .models import Syllabus, Topic

logger = logging.getLogger(__name__)

class ResourceEngine:
    def __init__(self, session):
        self.session = session

    def map_resources(self, syllabus_id: int) -> Dict[str, Dict[str, List[str]]]:
        """
        Maps syllabus topics to appropriate learning resources.
        Distinguishes between COURSE-SPECIFIC and SUPPLEMENTARY sources.
        """
        topics = self.session.query(Topic).join(Topic.unit).filter_by(syllabus_id=syllabus_id).all()
        
        resource_map = {}
        for topic in topics:
            resource_map[topic.title] = {
                "COURSE_SPECIFIC": [f"Lecture slides for {topic.title}"],
                "SUPPLEMENTARY": [f"External video tutorial for {topic.title}", "Wikipedia article"]
            }
            
        return resource_map
