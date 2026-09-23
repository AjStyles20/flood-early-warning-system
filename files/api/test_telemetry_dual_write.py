"""Tests for DB-3 legacy telemetry -> normalized observation dual-write."""

import os
import tempfile
import unittest
from datetime import datetime, timezone


class TelemetryDualWriteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ["FLOOD_EWS_DATABASE_URL"] = f"sqlite:///{cls.temp_dir.name}/dual_write.db"
        import database
        import models
        import telemetry_repository
        cls.database, cls.models, cls.repo = database, models, telemetry_repository
        models.Base.metadata.create_all(bind=database.engine)

    @classmethod
    def tearDownClass(cls):
        cls.database.engine.dispose(); cls.temp_dir.cleanup()

    def setUp(self):
        self.db = self.database.SessionLocal()
        for model in (self.models.Observation, self.models.Threshold, self.models.Dataset,
                      self.models.Station, self.models.Variable, self.models.DataSource,
                      self.models.TelemetryRecord):
            self.db.query(model).delete()
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def reading(self, source="hardware", rainfall=None, flow=None, battery=None):
        return self.models.TelemetryCreate(
            station_id="HW-01", station_name="Controlled prototype",
            data_source=source, lat=7.8, lon=6.7667,
            timestamp=datetime(2026, 9, 24, 0, 0, tzinfo=timezone.utc),
            water_level_m=1.42, danger_level_m=2.5,
            threshold_type="prototype_demo", rainfall_mm_hr=rainfall,
            flow_rate_m3s=flow, battery_pct=battery, signal="online",
        )

    def test_hardware_stage_only_creates_exactly_one_normalized_observation(self):
        legacy = self.repo.create_record(self.db, self.reading())
        rows = self.db.query(self.models.Observation).all()
        self.assertEqual(legacy.data_source, "hardware")
        self.assertEqual(len(rows), 1)
        variable = self.db.get(self.models.Variable, rows[0].variable_id)
        source = self.db.get(self.models.DataSource, rows[0].source_id)
        self.assertEqual(variable.code, "river_stage")
        self.assertEqual(source.code, "LOCAL_SENSOR")
        self.assertEqual(source.evidence_type, "observed")
        self.assertEqual(rows[0].value, legacy.water_level_m)
        self.assertIsNone(rows[0].dataset_id)

    def test_simulator_mirrors_only_values_actually_present(self):
        self.repo.create_record(self.db, self.reading(
            source="simulated", rainfall=4.2, flow=11.0, battery=87.0
        ))
        rows = self.db.query(self.models.Observation).all()
        codes = {self.db.get(self.models.Variable, row.variable_id).code for row in rows}
        self.assertEqual(codes, {"river_stage", "rainfall_rate", "river_discharge", "battery_pct"})
        source_codes = {self.db.get(self.models.DataSource, row.source_id).code for row in rows}
        self.assertEqual(source_codes, {"SIMULATED"})

    def test_threshold_is_not_misrepresented_as_observation(self):
        self.repo.create_record(self.db, self.reading())
        codes = {
            self.db.get(self.models.Variable, row.variable_id).code
            for row in self.db.query(self.models.Observation).all()
        }
        self.assertNotIn("threshold", codes)
        self.assertEqual(self.db.query(self.models.Threshold).count(), 0)


if __name__ == "__main__":
    unittest.main()
