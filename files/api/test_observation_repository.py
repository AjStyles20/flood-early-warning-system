"""Contract tests for the hardened normalized observation architecture."""

import os
import tempfile
import unittest
from datetime import datetime

from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError


class ObservationRepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ["FLOOD_EWS_DATABASE_URL"] = f"sqlite:///{cls.temp_dir.name}/observations.db"
        import database
        import models
        import observation_repository
        cls.database, cls.models, cls.repo = database, models, observation_repository
        models.Base.metadata.create_all(bind=database.engine)

    @classmethod
    def tearDownClass(cls):
        cls.database.engine.dispose(); cls.temp_dir.cleanup()

    def setUp(self):
        self.db = self.database.SessionLocal()
        for model in (self.models.Observation, self.models.Threshold, self.models.Dataset,
                      self.models.Station, self.models.Variable, self.models.DataSource):
            self.db.query(model).delete()
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_catalogue_seed_is_idempotent_and_provenance_is_explicit(self):
        self.repo.seed_catalogues(self.db)
        variables = self.db.query(self.models.Variable).count()
        sources = self.db.query(self.models.DataSource).count()
        self.repo.seed_catalogues(self.db)
        self.assertEqual(self.db.query(self.models.Variable).count(), variables)
        self.assertEqual(self.db.query(self.models.DataSource).count(), sources)
        self.assertEqual(self.repo.get_source(self.db, "SIMULATED").evidence_type, "simulated")
        self.assertEqual(self.repo.get_source(self.db, "REANALYSIS").evidence_type, "reanalysis")
        self.assertEqual(self.repo.get_source(self.db, "LOCAL_SENSOR").evidence_type, "observed")

    def test_atomic_stage_observation_does_not_require_unmeasured_variables(self):
        self.repo.seed_catalogues(self.db)
        station = self.models.Station(
            station_code="OBS-01", name="Observation test", latitude=7.8, longitude=6.7
        )
        self.db.add(station); self.db.commit(); self.db.refresh(station)
        stage = self.repo.get_variable(self.db, "river_stage")
        source = self.repo.get_source(self.db, "LOCAL_SENSOR")
        row = self.repo.create_observation(
            self.db, station=station, variable=stage, source=source,
            observed_at=datetime(2026, 9, 23, 21, 0), value=1.25, signal_status="online"
        )
        self.assertIsNone(row.dataset_id)
        self.assertEqual(self.db.query(self.models.Observation).count(), 1)
        self.assertEqual(row.value, 1.25)

    def test_composite_query_indexes_exist(self):
        indexes = {item["name"] for item in inspect(self.database.engine).get_indexes("observations")}
        self.assertIn("ix_observation_station_variable_time", indexes)
        self.assertIn("ix_observation_source_time", indexes)

    def test_threshold_unit_is_owned_by_variable(self):
        columns = {item["name"] for item in inspect(self.database.engine).get_columns("thresholds")}
        self.assertNotIn("unit", columns)


    def test_data_source_observational_flag_matches_evidence_type(self):
        self.repo.seed_catalogues(self.db)
        observed = self.repo.get_source(self.db, "LOCAL_SENSOR")
        simulated = self.repo.get_source(self.db, "SIMULATED")
        self.assertTrue(observed.is_observational)
        self.assertEqual(observed.evidence_type, "observed")
        self.assertFalse(simulated.is_observational)
        self.assertNotEqual(simulated.evidence_type, "observed")

        invalid = self.models.DataSource(
            code="INVALID_OBS_FLAG",
            name="Invalid source",
            evidence_type="simulated",
            provider="test",
            is_observational=True,
        )
        self.db.add(invalid)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()


if __name__ == "__main__":
    unittest.main()
