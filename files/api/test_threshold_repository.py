"""Tests for threshold typing, validity and provenance boundaries."""

import os
import tempfile
import unittest
from datetime import datetime


class ThresholdRepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ["FLOOD_EWS_DATABASE_URL"] = f"sqlite:///{cls.temp_dir.name}/thresholds.db"
        import database, models, threshold_repository
        cls.database, cls.models, cls.repo = database, models, threshold_repository
        models.Base.metadata.create_all(bind=database.engine)

    @classmethod
    def tearDownClass(cls):
        cls.database.engine.dispose(); cls.temp_dir.cleanup()

    def setUp(self):
        self.db = self.database.SessionLocal()
        for model in (self.models.Threshold, self.models.Observation, self.models.Station,
                      self.models.Variable, self.models.DataSource):
            self.db.query(model).delete()
        self.db.commit()
        self.station = self.models.Station(station_code="S1", name="S1", latitude=7.8, longitude=6.7)
        self.variable = self.models.Variable(code="stage_test", name="Stage", unit="m", category="hydrological")
        self.db.add_all([self.station, self.variable]); self.db.commit()

    def tearDown(self): self.db.close()

    def test_applicability_uses_validity_window(self):
        old = self.repo.stage_threshold(
            self.db, station=self.station, variable=self.variable,
            threshold_type="prototype_demo", value=2.0, source_reference="test",
            valid_to=datetime(2026, 1, 31),
        )
        current = self.repo.stage_threshold(
            self.db, station=self.station, variable=self.variable,
            threshold_type="prototype_demo", value=2.5, source_reference="test",
            valid_from=datetime(2026, 2, 1),
        )
        self.db.commit()
        self.assertEqual(self.repo.applicable_threshold(
            self.db, station_id=self.station.id, variable_id=self.variable.id,
            observed_at=datetime(2026, 1, 1)).id, old.id)
        self.assertEqual(self.repo.applicable_threshold(
            self.db, station_id=self.station.id, variable_id=self.variable.id,
            observed_at=datetime(2026, 3, 1)).id, current.id)

    def test_no_threshold_returns_none_instead_of_inventing_default(self):
        self.assertIsNone(self.repo.applicable_threshold(
            self.db, station_id=self.station.id, variable_id=self.variable.id,
            observed_at=datetime(2026, 3, 1)))


if __name__ == "__main__":
    unittest.main()
