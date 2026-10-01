from typing import List, Dict, Any

class StudentContextGatherer:
    def __init__(self):
        self.name = "StudentContextGatherer"

    def gather(self, user_id: str, course_id: str, unit_id: str, topic_id: str) -> Dict[str, Any]:
        """
        Tightly scopes academic context (USER -> COURSE -> UNIT -> TOPIC) 
        to prevent token bloat. Fetches only relevant notes, flashcards, and mistakes.
        """
        # Simulated DB fetch scoped precisely to the topic level
        relevant_notes = [f"Note on {topic_id} for {user_id}"]
        relevant_flashcards = [f"Flashcard on {topic_id} for {user_id}"]
        mistakes = [f"Mistake on {topic_id} for {user_id}"]

        return {
            "user_id": user_id,
            "course_id": course_id,
            "unit_id": unit_id,
            "topic_id": topic_id,
            "notes": relevant_notes,
            "flashcards": relevant_flashcards,
            "mistakes": mistakes
        }
