class AITutor:
    def __init__(self, knowledge_base):
        self.knowledge_base = knowledge_base

    def handle_intent(self, query, intent="Explain like I'm a beginner"):
        context = self.knowledge_base.get_context(query) if hasattr(self.knowledge_base, 'get_context') else "General Context"
        
        if intent == "Explain like I'm a beginner":
            return f"Simple explanation for {query} based on {context}"
        elif intent == "Derive step-by-step":
            return f"Step-by-step derivation for {query} based on {context}"
        elif intent == "Give me a hint":
            return f"Hint for {query} based on {context}"
        else:
            return f"General tutor response for {query}"
