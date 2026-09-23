"""Contract tests for the normalized observation/provenance schema."""

import os
import tempfile
import unittest
from datetime import datetime, timezone

from sqlalchemy import inspect


class NormalizedSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ["FLOOD_EWS_DATABASE_URL"] = f"sqlite:///{cls.temp_dir.name}/normalized.db"
        import database
        import models
        cls.database = database
        cls.models = models
        models.Base.metadata.create_all(bind=database.engine)

    @classmethod
    def tearDownClass(cls):
        cls.database.engine.dispose()
        cls.temp_dir.cleanup()

    def setUp(self):
        self.db = self.database.SessionLocal()

    def tearDown(self):
        self.db.rollback()
        self.db.close()

    def test_normalized_tables_exist_without_removing_legacy_telemetry(self):
        tables = set(inspect(self.database.engine).get_table_names())
        expected = {"stations", "variables", "data_sources", "datasets",
                    "observations", "thresholds", "telemetry"}
        self.assertTrue(expected.issubset(tables))

    def test_stage_only_observation_needs_no_fabricated_rainfall_or_flow(self):
        m = self.models
        station = m.Station(station_code="PROTO-01", name="Controlled prototype",
                            latitude=7.8, longitude=6.7667, station_type="prototype")
        variable = m.Variable(code="river_stage", name="River/local stage",
                              unit="m", category="hydrological_response")
        source = m.DataSource(code="LOCAL_SENSOR", name="Local physical node",
                              evidence_type="observed", provider="FloodWatch",
                              is_observational=True)
        self.db.add_all([station, variable, source])
        self.db.flush()
        obs = m.Observation(station_id=station.id, variable_id=variable.id,
                            source_id=source.id,
                            observed_at=datetime(2026, 9, 23, 20, 0, tzinfo=timezone.utc),
                            value=1.42, quality_flag="controlled_prototype",
                            signal_status="online")
        self.db.add(obs)
        self.db.commit()
        saved = self.db.query(m.Observation).filter_by(id=obs.id).one()
        self.assertEqual(saved.value, 1.42)
        self.assertIsNone(saved.dataset_id)

    def test_threshold_is_separate_from_observation(self):
        m = self.models
        station = m.Station(station_code="T-01", name="Threshold test",
                            latitude=7.8, longitude=6.7667, station_type="prototype")
        variable = m.Variable(code="stage_test", name="Stage test",
                              unit="m", category="hydrological_response")
        self.db.add_all([station, variable])
        self.db.flush()
        threshold = m.Threshold(station_id=station.id, variable_id=variable.id,
                                threshold_type="prototype_demo", value=2.0,
                                source_reference="controlled prototype configuration")
        self.db.add(threshold)
        self.db.commit()
        self.assertEqual(self.db.query(m.Threshold).filter_by(id=threshold.id).one().value, 2.0)


if __name__ == "__main__":
    unittest.main()
