class ActiveRecallEngine:
    def __init__(self):
        self.history = []

    def generate_question(self, topic, q_type="conceptual"):
        if q_type == "conceptual":
            return f"Why is {topic} important?"
        elif q_type == "derivation":
            return f"Derive the main formula for {topic}."
        elif q_type == "definition":
            return f"Define {topic}."
        return f"What do you know about {topic}?"

    def track_correctness(self, topic, correctness, confidence):
        self.history.append({
            "topic": topic,
            "correctness": correctness,
            "confidence": confidence
        })
