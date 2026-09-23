"""Focused tests for the persistent alert workflow service."""

import os
import tempfile
import unittest


class AlertServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        os.environ["FLOOD_EWS_DATABASE_URL"] = f"sqlite:///{cls.temp_dir.name}/alerts.db"
        import alert_service
        import database
        import models
        cls.service, cls.database, cls.models = alert_service, database, models
        models.Base.metadata.create_all(bind=database.engine)

    @classmethod
    def tearDownClass(cls):
        cls.database.engine.dispose(); cls.temp_dir.cleanup()

    def setUp(self):
        self.db = self.database.SessionLocal()
        self.db.query(self.models.AlertAuditLog).delete()
        self.db.query(self.models.AlertEvent).delete()
        self.db.query(self.models.User).delete()
        self.db.commit()
        self.operator = self.models.User(
            first_name="Test", last_name="Operator", email="alert-operator@example.com",
            phone_number="+2348000000000", password_hash="test", role="operator",
        )
        self.db.add(self.operator); self.db.commit(); self.db.refresh(self.operator)

    def tearDown(self):
        self.db.close()

    def test_low_state_does_not_create_alert(self):
        self.assertIsNone(self.service.persist_event(
            self.db, "A-01", "Station A", "hardware", "Low", "Continue monitoring."
        ))

    def test_active_alert_is_updated_not_duplicated(self):
        first = self.service.persist_event(
            self.db, "A-01", "Station A", "hardware", "Moderate", "Review conditions."
        )
        second = self.service.persist_event(
            self.db, "A-01", "Station A", "hardware", "High", "Exercise caution."
        )
        self.assertEqual(first.id, second.id)
        self.assertEqual(self.db.query(self.models.AlertEvent).count(), 1)
        self.assertEqual(second.risk_level, "High")
        self.assertTrue(second.message.endswith("follow official guidance."))

    def test_transition_rules_and_audit_are_preserved(self):
        alert = self.service.persist_event(
            self.db, "A-02", "Station B", "hardware", "High", "Review conditions."
        )
        public = self.service.change_status(
            self.db, alert.id, "acknowledged", "acknowledge", "Checked by operator", self.operator
        )
        self.assertEqual(public["status"], "acknowledged")
        public = self.service.change_status(
            self.db, alert.id, "resolved", "resolve", "Conditions reviewed", self.operator
        )
        self.assertEqual(public["status"], "resolved")
        audit = self.service.audit_trail(self.db, alert.id)
        self.assertEqual([row.action for row in audit], ["acknowledge", "resolve"])
        with self.assertRaises(self.service.InvalidAlertTransitionError):
            self.service.change_status(
                self.db, alert.id, "acknowledged", "acknowledge", "", self.operator
            )

    def test_unknown_alert_raises_domain_error(self):
        with self.assertRaises(self.service.AlertNotFoundError):
            self.service.audit_trail(self.db, 999999)


if __name__ == "__main__":
    unittest.main()
