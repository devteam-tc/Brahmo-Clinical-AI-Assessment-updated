"""Tests for Event-Sourced Regulatory Supersession DAG.
Verifies:
- EV001 -> EV002 (stay) -> EV003 (re-prohibited) supersession chain
- EV005 (restricted) -> EV006 (prohibited) supersession chain
- Point-in-time effective date checks
"""
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.connection import get_connection
from module_a.regulatory_register import RegulatoryRegister

class TestRegulatorySupersession(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = get_connection()
        cls.reg = RegulatoryRegister(cls.conn)

    def test_nimesulide_paracetamol_active_status(self):
        """As of today, Nimesulide + Paracetamol is PROHIBITED per EV003 GSR 411(E)."""
        verdict = self.reg.evaluate_target(["Nimesulide", "Paracetamol"], as_of_date="2026-10-15")
        self.assertTrue(verdict.is_prohibited)
        self.assertEqual(verdict.action, "PROHIBITED")
        self.assertEqual(verdict.notification_id, "GSR 411(E)")
        self.assertEqual(verdict.effective_date, "2023-06-15")
        self.assertIn("EV001", verdict.citation_text)
        self.assertIn("EV002", verdict.citation_text)
        self.assertIn("EV003", verdict.citation_text)

    def test_nimesulide_paracetamol_historical_stay_period(self):
        """During 2020 (between EV002 stay and EV003 re-prohibition), status was STAY_GRANTED."""
        verdict = self.reg.evaluate_target(["Nimesulide", "Paracetamol"], as_of_date="2020-01-01")
        self.assertEqual(verdict.action, "STAY_GRANTED")
        self.assertFalse(verdict.is_prohibited)
        self.assertEqual(verdict.notification_id, "HC-STAY-2019-114")

    def test_ranitidine_supersession(self):
        """Ranitidine was RESTRICTED (EV005), then superseded by PROHIBITED (EV006)."""
        verdict = self.reg.evaluate_target(["Ranitidine"], as_of_date="2026-10-15")
        self.assertTrue(verdict.is_prohibited)
        self.assertEqual(verdict.notification_id, "GSR 1012(E)")
        self.assertEqual(verdict.effective_date, "2025-02-01")

    def test_unrestricted_drug_returns_clean(self):
        """Amoxicillin has no prohibitive gazette events -> UNRESTRICTED."""
        verdict = self.reg.evaluate_target(["Amoxicillin"], as_of_date="2026-10-15")
        self.assertEqual(verdict.action, "UNRESTRICTED")
        self.assertFalse(verdict.is_prohibited)
        self.assertFalse(verdict.is_restricted)

if __name__ == "__main__":
    unittest.main()
