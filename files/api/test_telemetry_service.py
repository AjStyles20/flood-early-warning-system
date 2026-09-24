"""Focused tests for telemetry application-service orchestration."""

import os
import tempfile
import unittest
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Event
from unittest.mock import patch


class TelemetryServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ["FLOOD_EWS_DATABASE_URL"] = f"sqlite:///{cls.temp_dir.name}/telemetry_service.db"
        import database, models, telemetry_service, alert_service
        cls.database, cls.models, cls.service = database, models, telemetry_service
        cls.alert_service = alert_service
        models.Base.metadata.create_all(bind=database.engine)

    @classmethod
    def tearDownClass(cls):
        cls.database.engine.dispose(); cls.temp_dir.cleanup()

    def setUp(self):
        self.db = self.database.SessionLocal()
        for model in (self.models.AlertAuditLog, self.models.AlertEvent,
                      self.models.Observation, self.models.Threshold, self.models.Dataset,
                      self.models.Station, self.models.Variable, self.models.DataSource,
                      self.models.TelemetryRecord):
            self.db.query(model).delete()
        self.db.commit()
        self.alerts = []

    def tearDown(self): self.db.close()

    def reading(self, source="hardware", minute=1, level=1.6):
        return self.models.TelemetryCreate(
            station_id="SERVICE-01", station_name="Service station", data_source=source,
            lat=7.8, lon=6.7667,
            timestamp=datetime(2026, 9, 24, 4, minute, tzinfo=timezone.utc),
            water_level_m=level, danger_level_m=2.0, threshold_type="prototype_demo",
            rainfall_mm_hr=None if source == "hardware" else 2.0,
            flow_rate_m3s=None if source == "hardware" else 4.0,
            battery_pct=None, signal="online",
        )

    def persist_alert(self, db, station_id, station_name, source, risk, message, channels=None):
        self.alerts.append((station_id, source, risk, message))

    def test_ingest_owns_dual_write_and_immediate_alert_orchestration(self):
        row = self.service.ingest(self.db, self.reading(), persist_alert_event=self.persist_alert)
        self.assertEqual(row.data_source, "hardware")
        self.assertEqual(self.db.query(self.models.TelemetryRecord).count(), 1)
        self.assertEqual(self.db.query(self.models.Observation).count(), 1)
        self.assertEqual(len(self.alerts), 1)
        self.assertEqual(self.alerts[0][2], "High")

    def test_risk_statuses_reads_normalized_current_state(self):
        self.service.ingest(self.db, self.reading(minute=1, level=0.8), persist_alert_event=self.persist_alert)
        self.service.ingest(self.db, self.reading(minute=2, level=1.6), persist_alert_event=self.persist_alert)
        statuses = self.service.risk_statuses(
            self.db, data_source="hardware", language="en",
            alert_channels={"web": "available", "email": "simulated", "sms": "simulated"},
            risk_rank={"Low": 0, "Moderate": 1, "High": 2, "Severe": 3},
        )
        self.assertEqual(len(statuses), 1)
        self.assertEqual(statuses[0].risk_level, "High")
        self.assertEqual(statuses[0].rate_of_rise_m, 0.8)
        self.assertIsNone(statuses[0].ml_probability)

    def test_provider_attempts_only_for_new_alert_and_risk_escalation(self):
        outcomes = {"web": "available", "email": "sent", "sms": "not_configured"}
        with patch.object(self.service.notifications, "notify", return_value=outcomes) as notify:
            for minute, level in ((1, 1.2), (2, 1.4), (3, 1.7), (4, 1.8)):
                self.service.ingest(
                    self.db, self.reading(minute=minute, level=level),
                    persist_alert_event=self.alert_service.persist_event,
                )
            self.assertEqual(notify.call_count, 2)
            alert = self.db.query(self.models.AlertEvent).one()
            self.assertEqual(alert.risk_level, "High")
            self.assertEqual(__import__("json").loads(alert.channels_json), outcomes)

    def test_concurrent_ingest_claims_one_dispatch(self):
        # Seed the station before racing two different observations; this test
        # isolates dispatch coordination from station-creation coordination.
        self.service.ingest(self.db, self.reading(minute=1, level=0.2),
                            persist_alert_event=self.alert_service.persist_event)
        entered = Event()
        calls = []

        def slow_notify(*args, **kwargs):
            calls.append(args[0])
            entered.set()
            time.sleep(0.2)
            return {"web": "available", "email": "sent", "sms": "not_configured"}

        def ingest(minute):
            db = self.database.SessionLocal()
            try:
                self.service.ingest(db, self.reading(minute=minute, level=1.6),
                                    persist_alert_event=self.alert_service.persist_event)
            finally:
                db.close()

        with patch.object(self.service.notifications, "notify", side_effect=slow_notify):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(ingest, 2)
                self.assertTrue(entered.wait(3), "first dispatch did not start")
                second = pool.submit(ingest, 3)
                first.result(timeout=8)
                second.result(timeout=8)
        self.assertEqual(len(calls), 1)
        self.db.expire_all()
        self.assertEqual(self.db.query(self.models.AlertEvent).count(), 1)


if __name__ == "__main__":
    unittest.main()
