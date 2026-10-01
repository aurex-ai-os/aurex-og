class AcademicIntegrityGuard:
    def __init__(self):
        self.forbidden_patterns = ["give me the answer", "direct answer", "solve this for me"]

    def intercept(self, request_text):
        lower_req = request_text.lower()
        if any(pattern in lower_req for pattern in self.forbidden_patterns):
            return "I cannot provide direct answers for graded work. Let's explore the concepts together. What part of the problem are you struggling with?"
        return None
