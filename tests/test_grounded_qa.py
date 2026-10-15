"""Tests for Grounded Clinical Q&A, Citations, and Safety Fences.
Verifies:
- Claim-level citations [DocCode, Section, Page]
- Law 12 dose non-calculation fence
- Clean abstention on unsupported topics (migraine, TB)
- Conflict presentation (both editions with dates shown)
"""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from module_b.answering import GroundedAnsweringEngine

class TestGroundedQA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = GroundedAnsweringEngine()

    def test_q1_acute_otitis_media_citations(self):
        ans = self.engine.answer_question("What is the first-line antibiotic, dose basis, and duration for acute otitis media in a child?")
        self.assertEqual(ans.state, "ANSWERED")
        self.assertTrue(len(ans.citations) > 0)
        self.assertIn("STW-PED-01", ans.citations[0])
        self.assertIn("40 mg/kg/day", ans.answer_text)
        self.assertIn("5 days", ans.answer_text)

    def test_q2_pneumonia_dose_fence_no_calculation(self):
        """Law 12: Must retrieve dose text as written; never calculate for specific patient."""
        ans = self.engine.answer_question("A 6-year-old with non-severe community pneumonia: what is the amoxicillin dose exactly as the workflow states it?")
        self.assertEqual(ans.state, "ANSWERED")
        self.assertTrue(ans.is_dose_question)
        self.assertIn("40 mg/kg/day in three divided doses for 5 days", ans.answer_text)
        self.assertIn("Law 12", ans.answer_text)

    def test_q3_hypertension_conflict_supersession(self):
        """Must show both 2025 and 2021 editions with dates and supersession link."""
        ans = self.engine.answer_question("What is the first-line initial drug therapy for newly diagnosed adult hypertension?")
        self.assertEqual(ans.state, "ANSWERED")
        self.assertTrue(ans.conflict_detected)
        self.assertIn("2025", ans.answer_text)
        self.assertIn("2021", ans.answer_text)
        self.assertIn("Amlodipine", ans.answer_text)
        self.assertIn("Atenolol", ans.answer_text)

    def test_q9_migraine_clean_abstention(self):
        """Migraine is absent from corpus -> clean abstention stating what is missing."""
        ans = self.engine.answer_question("What is the first-line prophylactic drug for migraine in adults?")
        self.assertEqual(ans.state, "ABSTAINED")
        self.assertIn("ABSTAIN", ans.answer_text)
        self.assertIn("Migraine", ans.answer_text)
        self.assertEqual(len(ans.citations), 0)

    def test_q10_tuberculosis_clean_abstention(self):
        """Tuberculosis is absent from corpus -> clean abstention stating what is missing."""
        ans = self.engine.answer_question("What is the standard drug regimen for newly diagnosed pulmonary tuberculosis?")
        self.assertEqual(ans.state, "ABSTAINED")
        self.assertIn("ABSTAIN", ans.answer_text)
        self.assertIn("tuberculosis", ans.answer_text.lower())
        self.assertEqual(len(ans.citations), 0)

    def test_q11_clinic_protocol_labeling_and_divergence(self):
        """Clinic protocol must be labeled Sunrise Clinic SOP-CLIN-014 and contrasted with national STW."""
        ans = self.engine.answer_question("Per the clinic's own protocol, when are empirical antibiotics started in adult acute undifferentiated fever — and does the national workflow pack say the same?")
        self.assertEqual(ans.state, "ANSWERED")
        self.assertTrue(ans.contains_local_protocol)
        self.assertIn("SOP-CLIN-014", ans.answer_text)
        self.assertIn("Day 2", ans.answer_text)
        self.assertIn("Azithromycin", ans.answer_text)

if __name__ == "__main__":
    unittest.main()
