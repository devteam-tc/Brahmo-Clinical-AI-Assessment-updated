"""Tests for FDC Decomposition and Ambiguity Review Queue.
Adheres to Gate G2 (Decomposition accuracy >= 95%) and Gate G3 (Zero silent resolutions).
"""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.connection import get_connection
from module_a.normalization import DrugNormalizer

class TestFDCAndAmbiguity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = get_connection()
        cls.normalizer = DrugNormalizer(cls.conn)

    def test_fdc_count_in_registry_exceeds_100(self):
        """Gate G2: At least 100 real FDC products decomposed into salts + strengths."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM fdc_decomposition_registry WHERE ingredient_count >= 2;")
        count = cursor.fetchone()[0]
        self.assertGreaterEqual(count, 100, f"Expected >= 100 FDCs in registry, got {count}")

    def test_sample_fdc_decompositions(self):
        """Verifies specific FDCs decomposed accurately with salt + strength."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT decomposition_summary FROM fdc_decomposition_registry WHERE brand_name = 'Sinarest Tablet';")
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        summary = row[0]
        self.assertIn("Paracetamol 500 mg", summary)
        self.assertIn("Chlorpheniramine 2 mg", summary)
        self.assertIn("Phenylephrine 10 mg", summary)

    def test_zero_silent_resolutions_on_ambiguous_brand(self):
        """Gate G3: Telma without strength must land in review queue with reason code."""
        res = self.normalizer.normalize("Telma", None)
        self.assertEqual(res.status, "QUEUED_FOR_REVIEW")
        self.assertEqual(res.reason_code, "AMBIGUOUS_STRENGTH_MULTIPLE_MATCHES")
        self.assertIsNotNone(res.review_queue_id)

    def test_zero_silent_resolutions_on_unknown_brand(self):
        """Gate G3: Zqtrixon Forte must land in review queue with UNRECOGNIZED_BRAND."""
        res = self.normalizer.normalize("Zqtrixon Forte", None)
        self.assertEqual(res.status, "QUEUED_FOR_REVIEW")
        self.assertEqual(res.reason_code, "UNRECOGNIZED_BRAND")
        self.assertEqual(res.confidence, 0.0)

if __name__ == "__main__":
    unittest.main()
