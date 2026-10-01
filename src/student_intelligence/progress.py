class ProgressReporter:
    def __init__(self):
        self.metrics = {}

    def update_metrics(self, student_id, syllabus_coverage, mastery_score):
        self.metrics[student_id] = {
            "Syllabus coverage": syllabus_coverage,
            "Demonstrated mastery": mastery_score
        }

    def generate_report(self, student_id):
        if student_id not in self.metrics:
            return "No verifiable metrics available."
        data = self.metrics[student_id]
        return f"Syllabus coverage: {data['Syllabus coverage']}%, Demonstrated mastery: {data['Demonstrated mastery']}%"
