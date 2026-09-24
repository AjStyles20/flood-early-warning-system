"""Database-level coordinate integrity tests for normalized stations."""

import os
import tempfile
import unittest

from sqlalchemy.exc import IntegrityError


class StationCoordinateConstraintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ["FLOOD_EWS_DATABASE_URL"] = f"sqlite:///{cls.temp_dir.name}/coordinates.db"
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
        self.db.query(self.models.Station).delete()
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def _station(self, code, lat, lon):
        return self.models.Station(
            station_code=code,
            name=code,
            latitude=lat,
            longitude=lon,
            station_type="test",
        )

    def test_boundary_coordinates_are_valid(self):
        self.db.add(self._station("BOUNDARY-A", -90.0, -180.0))
        self.db.add(self._station("BOUNDARY-B", 90.0, 180.0))
        self.db.commit()
        self.assertEqual(self.db.query(self.models.Station).count(), 2)

    def test_invalid_latitude_is_rejected(self):
        self.db.add(self._station("BAD-LAT", 90.0001, 6.7))
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    def test_invalid_longitude_is_rejected(self):
        self.db.add(self._station("BAD-LON", 7.8, -180.0001))
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()


if __name__ == "__main__":
    unittest.main()
