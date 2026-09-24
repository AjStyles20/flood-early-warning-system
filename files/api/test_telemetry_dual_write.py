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

    def test_threshold_is_configuration_not_observation(self):
        self.repo.create_record(self.db, self.reading())
        codes = {
            self.db.get(self.models.Variable, row.variable_id).code
            for row in self.db.query(self.models.Observation).all()
        }
        self.assertNotIn("threshold", codes)
        threshold = self.db.query(self.models.Threshold).one()
        self.assertEqual(threshold.value, 2.5)
        self.assertEqual(threshold.threshold_type, "prototype_demo")
        self.assertIn("not independently verified", threshold.source_reference)

    def test_repeated_identical_compatibility_threshold_is_reused(self):
        self.repo.create_record(self.db, self.reading())
        later = self.reading()
        later.timestamp = datetime(2026, 9, 24, 0, 1, tzinfo=timezone.utc)
        self.repo.create_record(self.db, later)
        self.assertEqual(self.db.query(self.models.Threshold).count(), 1)


    def test_generic_ingestion_cannot_create_official_threshold_authority(self):
        reading = self.reading()
        reading.threshold_type = "official_operational"
        self.repo.create_record(self.db, reading)
        threshold = self.db.query(self.models.Threshold).one()
        self.assertEqual(threshold.threshold_type, "prototype_demo")
        self.assertIn("not an authorized official-threshold channel", threshold.source_reference)
        self.assertEqual(
            self.db.query(self.models.Threshold)
            .filter(self.models.Threshold.threshold_type == "official_operational")
            .count(),
            0,
        )


    def test_generic_ingestion_cannot_create_research_statistical_threshold_authority(self):
        reading = self.reading()
        reading.threshold_type = "research_statistical"
        self.repo.create_record(self.db, reading)
        threshold = self.db.query(self.models.Threshold).one()
        self.assertEqual(threshold.threshold_type, "prototype_demo")
        self.assertIn("not an authorized threshold-evidence channel", threshold.source_reference)
        self.assertEqual(
            self.db.query(self.models.Threshold)
            .filter(self.models.Threshold.threshold_type == "research_statistical")
            .count(),
            0,
        )


    def test_threshold_change_creates_temporal_change_point_and_preserves_history(self):
        first = self.reading()
        first.timestamp = datetime(2026, 9, 24, 0, 0, tzinfo=timezone.utc)
        first.danger_level_m = 2.0
        self.repo.create_record(self.db, first)

        second = self.reading()
        second.timestamp = datetime(2026, 9, 24, 1, 0, tzinfo=timezone.utc)
        second.danger_level_m = 2.5
        self.repo.create_record(self.db, second)

        rows = self.db.query(self.models.Threshold).order_by(self.models.Threshold.valid_from.asc()).all()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].value, 2.0)
        self.assertEqual(rows[0].valid_from, first.timestamp.replace(tzinfo=None))
        self.assertLess(rows[0].valid_to, second.timestamp.replace(tzinfo=None))
        self.assertEqual(rows[1].value, 2.5)
        self.assertEqual(rows[1].valid_from, second.timestamp.replace(tzinfo=None))
        self.assertIsNone(rows[1].valid_to)

        import threshold_repository
        station = self.db.query(self.models.Station).filter(self.models.Station.station_code == "HW-01").one()
        variable = self.db.query(self.models.Variable).filter(self.models.Variable.code == "river_stage").one()
        old = threshold_repository.applicable_threshold(
            self.db, station_id=station.id, variable_id=variable.id,
            observed_at=first.timestamp,
        )
        current = threshold_repository.applicable_threshold(
            self.db, station_id=station.id, variable_id=variable.id,
            observed_at=second.timestamp,
        )
        self.assertEqual(old.value, 2.0)
        self.assertEqual(current.value, 2.5)


    def test_exact_normalized_replay_is_idempotent_but_conflicting_duplicate_is_rejected(self):
        first = self.reading()
        self.repo.create_record(self.db, first)
        self.assertEqual(self.db.query(self.models.Observation).count(), 1)

        # A transport retry with the exact same evidence must not create a
        # second normalized observation.
        self.repo.create_record(self.db, self.reading())
        self.assertEqual(self.db.query(self.models.Observation).count(), 1)

        conflict = self.reading()
        conflict.water_level_m = 1.99
        with self.assertRaises(ValueError):
            self.repo.create_record(self.db, conflict)
        self.db.rollback()
        self.assertEqual(self.db.query(self.models.Observation).count(), 1)


if __name__ == "__main__":
    unittest.main()
