"""Temporal metadata integrity tests for normalized Dataset and Threshold."""

import os
import tempfile
import unittest
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError


class TemporalMetadataConstraintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ["FLOOD_EWS_DATABASE_URL"] = f"sqlite:///{cls.temp_dir.name}/temporal.db"
        import database
        import models
        cls.database, cls.models = database, models
        models.Base.metadata.create_all(bind=database.engine)

    @classmethod
    def tearDownClass(cls):
        cls.database.engine.dispose()
        cls.temp_dir.cleanup()

    def setUp(self):
        self.db = self.database.SessionLocal()
        for model in (self.models.Threshold, self.models.Dataset, self.models.Station, self.models.Variable):
            self.db.query(model).delete()
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_dataset_rejects_reversed_coverage_interval(self):
        end = datetime(2026, 1, 1)
        row = self.models.Dataset(
            dataset_code="BAD-COVERAGE", title="Bad coverage", provider="test",
            evidence_type="observed", redistribution_status="restricted",
            coverage_start=end + timedelta(days=1), coverage_end=end,
        )
        self.db.add(row)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    def test_dataset_rejects_unknown_evidence_type(self):
        row = self.models.Dataset(
            dataset_code="BAD-TYPE", title="Bad type", provider="test",
            evidence_type="authoritative-ish", redistribution_status="restricted",
        )
        self.db.add(row)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    def test_threshold_rejects_reversed_validity_interval(self):
        station = self.models.Station(
            station_code="TEMP-01", name="Temporal station", latitude=7.8, longitude=6.7
        )
        variable = self.models.Variable(
            code="TEMP-STAGE", name="Stage", unit="m", category="hydrology"
        )
        self.db.add_all([station, variable]); self.db.commit()
        start = datetime(2026, 9, 24, 2, 0)
        row = self.models.Threshold(
            station_id=station.id, variable_id=variable.id,
            threshold_type="prototype_demo", value=2.5,
            valid_from=start, valid_to=start - timedelta(seconds=1), active=True,
        )
        self.db.add(row)
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()


if __name__ == "__main__":
    unittest.main()
