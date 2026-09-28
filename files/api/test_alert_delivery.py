"""Provider-contract tests for FloodWatch alert delivery.

These tests never contact Twilio or EmailJS. They verify configuration
detection, request construction, authentication and safe failure behavior.
"""

import base64
import os
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs

import alert_delivery


TWILIO_ENV = {
    "FLOOD_EWS_TWILIO_ACCOUNT_SID": "AC1234567890",
    "FLOOD_EWS_TWILIO_AUTH_TOKEN": "secret-token",
    "FLOOD_EWS_TWILIO_FROM_NUMBER": "+15005550006",
    "FLOOD_EWS_ALERT_SMS_TO": "+2348000000000",
}

EMAIL_ENV = {
    "FLOOD_EWS_EMAILJS_SERVICE_ID": "service_test",
    "FLOOD_EWS_EMAILJS_ALERT_TEMPLATE_ID": "template_alert",
    "FLOOD_EWS_EMAILJS_PUBLIC_KEY": "public_test",
    "FLOOD_EWS_ALERT_EMAIL_TO": "alerts@example.com",
}


class FakeResponse:
    def __init__(self, status=201, body=b"{}"):
        self.status = status
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._body


class AlertDeliveryContractTests(unittest.TestCase):
    def setUp(self):
        self.names = set(TWILIO_ENV) | set(EMAIL_ENV) | {"FLOOD_EWS_EMAILJS_PRIVATE_KEY"}
        self.previous = {name: os.environ.get(name) for name in self.names}
        for name in self.names:
            os.environ.pop(name, None)

    def tearDown(self):
        for name, value in self.previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def test_capabilities_are_explicit_when_unconfigured(self):
        self.assertEqual(
            alert_delivery.capabilities(),
            {"web": "available", "email": "not_configured", "sms": "not_configured"},
        )
        self.assertEqual(alert_delivery.send_email("subject", "message"), "not_configured")
        self.assertEqual(alert_delivery.send_sms("message"), "not_configured")

    def test_twilio_request_uses_expected_endpoint_auth_and_form_fields(self):
        os.environ.update(TWILIO_ENV)
        captured = {}

        def fake_urlopen(req, timeout=0):
            captured["request"] = req
            captured["timeout"] = timeout
            return FakeResponse(status=201, body=b'{"sid":"SM123"}')

        with patch.object(alert_delivery.request, "urlopen", side_effect=fake_urlopen):
            result = alert_delivery.send_sms("FloodWatch test alert")

        self.assertEqual(result, "sent")
        req = captured["request"]
        self.assertEqual(
            req.full_url,
            "https://api.twilio.com/2010-04-01/Accounts/AC1234567890/Messages.json",
        )
        self.assertEqual(captured["timeout"], 10)
        expected_auth = base64.b64encode(b"AC1234567890:secret-token").decode()
        self.assertEqual(req.get_header("Authorization"), f"Basic {expected_auth}")
        self.assertEqual(req.get_header("Content-type"), "application/x-www-form-urlencoded")
        form = parse_qs(req.data.decode("utf-8"))
        self.assertEqual(form["From"], ["+15005550006"])
        self.assertEqual(form["To"], ["+2348000000000"])
        self.assertEqual(form["Body"], ["FloodWatch test alert"])

    def test_twilio_network_or_provider_exception_fails_closed(self):
        os.environ.update(TWILIO_ENV)
        with patch.object(alert_delivery.request, "urlopen", side_effect=OSError("offline")):
            self.assertEqual(alert_delivery.send_sms("test"), "failed")

    def test_emailjs_alert_request_uses_configured_recipient(self):
        os.environ.update(EMAIL_ENV)
        captured = {}

        def fake_post(url, payload, headers=None):
            captured["url"] = url
            captured["payload"] = payload
            captured["headers"] = headers
            return 200, "OK"

        with patch.object(alert_delivery, "_post_json", side_effect=fake_post):
            result = alert_delivery.send_email("FloodWatch High alert", "Review conditions.")

        self.assertEqual(result, "sent")
        self.assertEqual(captured["url"], "https://api.emailjs.com/api/v1.0/email/send")
        self.assertEqual(captured["payload"]["service_id"], "service_test")
        self.assertEqual(captured["payload"]["template_id"], "template_alert")
        self.assertEqual(captured["payload"]["user_id"], "public_test")
        self.assertEqual(captured["payload"]["template_params"]["to_email"], "alerts@example.com")
        self.assertEqual(captured["payload"]["template_params"]["subject"], "FloodWatch High alert")
        self.assertEqual(captured["payload"]["template_params"]["message"], "Review conditions.")

    def test_provider_failure_is_not_reported_as_sent(self):
        os.environ.update(EMAIL_ENV)
        with patch.object(alert_delivery, "_post_json", side_effect=OSError("offline")):
            self.assertEqual(alert_delivery.send_email("Subject", "Message"), "failed")

    def test_dispatch_reports_actual_provider_outcomes(self):
        with patch.object(alert_delivery, "send_email", return_value="sent"), patch.object(
            alert_delivery, "send_sms", return_value="failed"
        ):
            result = alert_delivery.dispatch("STN-01", "Lokoja", "High", "Review conditions.")
        self.assertEqual(result, {"web": "available", "email": "sent", "sms": "failed"})


if __name__ == "__main__":
    unittest.main()
