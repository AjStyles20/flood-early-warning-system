"""Migration guard: production modules must not reintroduce legacy telemetry reads.

TelemetryRecord remains a temporary dual-write rollback/reference store. This
test protects the architectural boundary while DB-5 retirement is still gated.
"""

from pathlib import Path
import re
import unittest


API_DIR = Path(__file__).resolve().parent
PRODUCTION_FILES = [
    API_DIR / "main.py",
    API_DIR / "telemetry_service.py",
    API_DIR / "normalized_read_repository.py",
    API_DIR / "normalized_current_state_service.py",
    API_DIR / "alert_service.py",
]


class LegacyTelemetryDependencyGuardTests(unittest.TestCase):
    def test_operational_modules_do_not_query_telemetry_record(self):
        violations = []
        query_pattern = re.compile(r"(db\.query\(models\.TelemetryRecord\)|query\(models\.TelemetryRecord\))")
        for path in PRODUCTION_FILES:
            text = path.read_text(encoding="utf-8")
            if query_pattern.search(text):
                violations.append(path.name)
        self.assertEqual(
            violations, [],
            f"Operational modules reintroduced direct TelemetryRecord reads: {violations}",
        )

    def test_main_has_no_telemetry_repository_read_dependency(self):
        text = (API_DIR / "main.py").read_text(encoding="utf-8")
        self.assertNotIn("import telemetry_repository", text)
        self.assertNotIn("latest_records_per_station", text)


if __name__ == "__main__":
    unittest.main()
