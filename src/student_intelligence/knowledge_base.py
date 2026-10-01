from rag_vector import get_embeddings

class KnowledgeBase:
    def __init__(self):
        self.store = {}

    def add_knowledge(self, key, text):
        self.store[key] = {
            "text": text,
            "embedding": get_embeddings(text)
        }
