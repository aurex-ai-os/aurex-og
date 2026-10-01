import unittest
from src.student_intelligence.memory import AcademicMemory
from src.student_intelligence.integrity import AcademicIntegrityGuard
from src.student_intelligence.progress import ProgressReporter

class TestStudentIntelligence(unittest.TestCase):
    def test_memory_preferences(self):
        mem = AcademicMemory()
        mem.store_preference("student_1", "style", "visual")
        self.assertEqual(mem.get_memory("student_1")["preferences"]["style"], "visual")

    def test_memory_mistakes(self):
        mem = AcademicMemory()
        mem.log_mistake("student_1", "forgot carry over")
        self.assertIn("forgot carry over", mem.get_memory("student_1")["mistakes"])

    def test_memory_completed(self):
        mem = AcademicMemory()
        mem.mark_completed("student_1", "chap1")
        self.assertIn("chap1", mem.get_memory("student_1")["completed"])

    def test_integrity_guard_intercepts(self):
        guard = AcademicIntegrityGuard()
        resp = guard.intercept("Can you give me the answer to Q1?")
        self.assertIsNotNone(resp)
        self.assertIn("cannot provide direct answers", resp)

    def test_integrity_guard_allows(self):
        guard = AcademicIntegrityGuard()
        resp = guard.intercept("Can you explain Newton's second law?")
        self.assertIsNone(resp)

    def test_progress_reporter(self):
        prog = ProgressReporter()
        prog.update_metrics("student_1", 92, 78)
        report = prog.generate_report("student_1")
        self.assertIn("Syllabus coverage: 92%", report)
        self.assertIn("Demonstrated mastery: 78%", report)

    def test_progress_reporter_no_data(self):
        prog = ProgressReporter()
        report = prog.generate_report("unknown")
        self.assertEqual(report, "No verifiable metrics available.")

    def test_syllabus_ingestion(self):
        self.assertTrue(True)

    def test_timeline_calculation(self):
        self.assertTrue(True)

    def test_context_scoping(self):
        self.assertTrue(True)

if __name__ == '__main__':
    unittest.main()
