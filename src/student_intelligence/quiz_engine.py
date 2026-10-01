class AdaptiveQuizEngine:
    MODES = ["Quick", "Topic", "Unit", "Mixed", "Weakness", "Exam-level"]

    def __init__(self):
        pass

    def build_quiz(self, mode):
        if mode not in self.MODES:
            raise ValueError(f"Invalid mode. Must be one of {self.MODES}")
        return {"mode": mode, "questions": []}

    def analyze_performance(self, results):
        return {
            "score": 80,
            "recommendation": "Review weak topics."
        }
