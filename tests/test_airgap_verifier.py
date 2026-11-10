"""Unit tests for Air-Gapped Zero-Install Portability Guard."""
import unittest
from statcraft.airgap_verifier import verify_airgap_integrity


class TestAirgapVerifier(unittest.TestCase):
    def test_airgap_audit_passes(self):
        audit = verify_airgap_integrity()
        self.assertEqual(audit["status"], "PASS")
        self.assertTrue(audit["air_gapped"])
        self.assertEqual(audit["external_sockets"], 0)
        self.assertGreaterEqual(len(audit["details"]), 4)
        self.assertTrue(any("Telemetry Radiosilence" in d for d in audit["details"]))


if __name__ == "__main__":
    unittest.main()
