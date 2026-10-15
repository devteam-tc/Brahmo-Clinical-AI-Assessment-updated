"""Unit and Integration Tests for Medication Safety Rail and 8-State Contract.
Adheres to Gate G4: Zero false negatives, all known-bad seeded cases flagged, unknowns rendered as unknowns.
"""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.connection import get_connection
from module_a.safety_rail import DeterministicSafetyRail, PrescriptionItem

class TestSafetyRails(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = get_connection()
        cls.rail = DeterministicSafetyRail(cls.conn)

    def test_rx01_duplicate_paracetamol_with_cumulative_exposure(self):
        """RX01: Dolo 650 + Sinarest Tablet -> Duplicate paracetamol + cumulative 2300 mg/day."""
        items = [
            PrescriptionItem(1, "Dolo 650", "650 mg", "1-0-1 x 5d", "fever"),
            PrescriptionItem(2, "Sinarest Tablet", None, "1-0-1 x 5d", "cold")
        ]
        res = self.rail.evaluate_prescription("TEST-RX01", items)
        self.assertEqual(res.overall_state, "HIT")
        self.assertIn("Paracetamol", res.summary_evidence)
        self.assertIn("2300 mg/day", res.summary_evidence)

    def test_rx02_prohibited_fdc_nimusulide_paracetamol(self):
        """RX02: NimuPar-P -> Banned FDC under GSR 411(E), EV003."""
        items = [
            PrescriptionItem(1, "NimuPar-P", None, "1-0-1 x 3d", "pain")
        ]
        res = self.rail.evaluate_prescription("TEST-RX02", items)
        self.assertEqual(res.overall_state, "HIT")
        self.assertEqual(res.highest_severity, "CRITICAL")
        self.assertIn("GSR 411(E)", res.summary_evidence)
        self.assertIn("PROHIBITED", res.summary_evidence)

    def test_rx03_severe_interaction_warfarin_azithromycin(self):
        """RX03: Warfarin + Azithromycin -> Severe interaction HIT."""
        items = [
            PrescriptionItem(1, "Warf 5", "5 mg", "0-0-1", "AF"),
            PrescriptionItem(2, "Azee 500", "500 mg", "1-0-0 x 3d", "RTI")
        ]
        res = self.rail.evaluate_prescription("TEST-RX03", items)
        self.assertEqual(res.overall_state, "HIT")
        self.assertEqual(res.highest_severity, "SEVERE")
        self.assertIn("bleeding", res.summary_evidence.lower())

    def test_rx04_ambiguous_strength_unverified_input(self):
        """RX04: Telma without strength -> UNVERIFIED_INPUT (never silently guesses)."""
        items = [
            PrescriptionItem(1, "Telma", None, "1-0-0", "HTN")
        ]
        res = self.rail.evaluate_prescription("TEST-RX04", items)
        self.assertEqual(res.overall_state, "UNVERIFIED_INPUT")
        self.assertFalse(res.items_verified)
        self.assertIn("AMBIGUOUS_STRENGTH_MULTIPLE_MATCHES", res.summary_evidence)

    def test_rx05_clean_prescription_checked_no_hit(self):
        """RX05: Glycomet 500 + Atorva 10 -> Clean case -> CHECKED_NO_HIT."""
        items = [
            PrescriptionItem(1, "Glycomet 500", "500 mg", "1-0-1", "T2DM"),
            PrescriptionItem(2, "Atorva 10", "10 mg", "0-0-1", "lipids")
        ]
        res = self.rail.evaluate_prescription("TEST-RX05", items)
        self.assertEqual(res.overall_state, "CHECKED_NO_HIT")
        self.assertEqual(res.highest_severity, "INFO")
        self.assertTrue(res.items_verified)

    def test_rx08_unrecognized_brand_unverified_input(self):
        """RX08: Zqtrixon Forte -> Unknown brand -> UNVERIFIED_INPUT."""
        items = [
            PrescriptionItem(1, "Zqtrixon Forte", None, "1-0-1", "as written")
        ]
        res = self.rail.evaluate_prescription("TEST-RX08", items)
        self.assertEqual(res.overall_state, "UNVERIFIED_INPUT")
        self.assertIn("UNRECOGNIZED_BRAND", res.summary_evidence)

if __name__ == "__main__":
    unittest.main()
