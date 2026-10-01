class GapDetector:
    def __init__(self, topic_graph):
        self.topic_graph = topic_graph

    def trace_mistakes(self, repeated_mistakes):
        missing_prerequisites = set()
        for mistake_topic in repeated_mistakes:
            # Assuming topic_graph has a method to get prerequisites
            if hasattr(self.topic_graph, 'get_prerequisites'):
                prereqs = self.topic_graph.get_prerequisites(mistake_topic)
                missing_prerequisites.update(prereqs)
        
        return list(missing_prerequisites)
