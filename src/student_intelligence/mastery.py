class MasteryEngine:
    STATES = [
        "NOT_STARTED",
        "INTRODUCED",
        "DEVELOPING",
        "FUNCTIONAL",
        "STRONG",
        "MASTERED"
    ]

    def __init__(self):
        self.topic_states = {}

    def update_mastery(self, topic, active_recall_signals, quiz_signals, exam_signals):
        # Synthesize signals to update state
        current_idx = self.topic_states.get(topic, 0)
        # Dummy logic to advance state
        if current_idx < len(self.STATES) - 1:
            self.topic_states[topic] = current_idx + 1
        
        return self.STATES[self.topic_states[topic]]
