"""Tests for real-provider alert adapters without making network calls."""

import os
import unittest
from unittest.mock import patch

import alert_delivery


class AlertDeliveryTests(unittest.TestCase):
    def test_unconfigured_is_explicit(self):
        names = [
            "FLOOD_EWS_EMAILJS_SERVICE_ID", "FLOOD_EWS_EMAILJS_ALERT_TEMPLATE_ID",
            "FLOOD_EWS_EMAILJS_PUBLIC_KEY", "FLOOD_EWS_ALERT_EMAIL_TO",
            "FLOOD_EWS_TWILIO_ACCOUNT_SID", "FLOOD_EWS_TWILIO_AUTH_TOKEN",
            "FLOOD_EWS_TWILIO_FROM_NUMBER", "FLOOD_EWS_ALERT_SMS_TO",
        ]
        with patch.dict(os.environ, {name: "" for name in names}):
            self.assertEqual(alert_delivery.capabilities(), {
                "web": "available", "email": "not_configured", "sms": "not_configured"
            })

    def test_emailjs_dispatch_reports_sent_only_after_provider_success(self):
        env = {
            "FLOOD_EWS_EMAILJS_SERVICE_ID": "service-test",
            "FLOOD_EWS_EMAILJS_ALERT_TEMPLATE_ID": "template-test",
            "FLOOD_EWS_EMAILJS_PUBLIC_KEY": "public-test",
            "FLOOD_EWS_ALERT_EMAIL_TO": "recipient@example.com",
        }
        with patch.dict(os.environ, env), patch.object(alert_delivery, "_post_json", return_value=(200, "OK")) as post:
            self.assertEqual(alert_delivery.send_email("Subject", "Message"), "sent")
            payload = post.call_args.args[1]
            self.assertEqual(payload["template_params"]["to_email"], "recipient@example.com")

    def test_provider_failure_is_not_reported_as_sent(self):
        env = {
            "FLOOD_EWS_EMAILJS_SERVICE_ID": "service-test",
            "FLOOD_EWS_EMAILJS_ALERT_TEMPLATE_ID": "template-test",
            "FLOOD_EWS_EMAILJS_PUBLIC_KEY": "public-test",
            "FLOOD_EWS_ALERT_EMAIL_TO": "recipient@example.com",
        }
        with patch.dict(os.environ, env), patch.object(alert_delivery, "_post_json", side_effect=OSError("offline")):
            self.assertEqual(alert_delivery.send_email("Subject", "Message"), "failed")


if __name__ == "__main__":
    unittest.main()
