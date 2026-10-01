class AcademicMemory:
    def __init__(self):
        self.learning_preferences = {}
        self.recurring_mistakes = []
        self.completed_resources = set()

    def store_preference(self, student_id, preference, value):
        if student_id not in self.learning_preferences:
            self.learning_preferences[student_id] = {}
        self.learning_preferences[student_id][preference] = value

    def log_mistake(self, student_id, mistake):
        self.recurring_mistakes.append({"student_id": student_id, "mistake": mistake})

    def mark_completed(self, student_id, resource_id):
        self.completed_resources.add((student_id, resource_id))

    def get_memory(self, student_id):
        return {
            "preferences": self.learning_preferences.get(student_id, {}),
            "mistakes": [m["mistake"] for m in self.recurring_mistakes if m["student_id"] == student_id],
            "completed": [r for s, r in self.completed_resources if s == student_id]
        }
