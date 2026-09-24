"""DB-5 readiness audit.

This test does NOT authorize or perform legacy telemetry retirement. It makes
the remaining retirement prerequisites executable and prevents accidental
removal while the physical post-migration regression is still pending.
"""

from pathlib import Path
import re
import unittest


API_DIR = Path(__file__).resolve().parent
REPO_ROOT = API_DIR.parent.parent
PRODUCTION_FILES = [
    API_DIR / "main.py",
    API_DIR / "telemetry_service.py",
    API_DIR / "normalized_read_repository.py",
    API_DIR / "normalized_current_state_service.py",
    API_DIR / "alert_service.py",
]
PHYSICAL_VERIFIER = REPO_ROOT / "files" / "hardware" / "verify_physical_hardware_regression.py"
HARDWARE_GUIDE = REPO_ROOT / "files" / "docs" / "hardware_integration_guide.md"


class DB5ReadinessTests(unittest.TestCase):
    def test_legacy_model_still_exists_until_retirement_is_authorized(self):
        import models
        self.assertTrue(
            hasattr(models, "TelemetryRecord"),
            "DB-5 was performed without the explicit retirement gate.",
        )

    def test_production_modules_have_no_direct_legacy_reads(self):
        pattern = re.compile(r"db\.query\(models\.TelemetryRecord\)")
        violations = [
            path.name for path in PRODUCTION_FILES
            if pattern.search(path.read_text(encoding="utf-8"))
        ]
        self.assertEqual(violations, [])

    def test_dual_write_still_exists_as_rollback_evidence(self):
        text = (API_DIR / "telemetry_repository.py").read_text(encoding="utf-8")
        self.assertIn("models.TelemetryRecord(**reading.model_dump())", text)
        self.assertIn("stage_normalized_mirror", text)

    def test_physical_regression_gate_is_prepared_but_not_faked_by_ci(self):
        self.assertTrue(PHYSICAL_VERIFIER.exists())
        verifier = PHYSICAL_VERIFIER.read_text(encoding="utf-8")
        guide = HARDWARE_GUIDE.read_text(encoding="utf-8")
        self.assertIn("PHYSICAL_REGRESSION_DB_PATH_PASS", verifier)
        self.assertIn("Pico analogue input", guide)
        self.assertIn("HTTP 200", guide)
        self.assertIn("dashboard", guide.lower())


if __name__ == "__main__":
    unittest.main()
