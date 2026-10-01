class ExamSimulator:
    def __init__(self):
        pass

    def build_mock(self, full=True, timed=True):
        return {
            "type": "Full Mock" if full else "Partial Mock",
            "timed": timed,
            "questions": []
        }

    def label_question(self, is_past_question):
        if is_past_question:
            return "REAL PAST QUESTION"
        return "AI-GENERATED PRACTICE QUESTION"
