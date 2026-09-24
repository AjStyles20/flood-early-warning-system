"""Real alert-delivery adapters for FloodWatch.

Providers are configured only through environment variables. Missing providers
remain explicit rather than silently pretending that a message was sent.
"""

import base64
import json
import os
from urllib import parse, request


def _post_json(url: str, payload: dict, headers: dict | None = None) -> tuple[int, str]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json", **(headers or {})})
    with request.urlopen(req, timeout=10) as response:
        return response.status, response.read().decode("utf-8", errors="replace")


def email_configured() -> bool:
    return all(os.getenv(name, "").strip() for name in (
        "FLOOD_EWS_EMAILJS_SERVICE_ID",
        "FLOOD_EWS_EMAILJS_ALERT_TEMPLATE_ID",
        "FLOOD_EWS_EMAILJS_PUBLIC_KEY",
        "FLOOD_EWS_ALERT_EMAIL_TO",
    ))


def sms_configured() -> bool:
    return all(os.getenv(name, "").strip() for name in (
        "FLOOD_EWS_TWILIO_ACCOUNT_SID",
        "FLOOD_EWS_TWILIO_AUTH_TOKEN",
        "FLOOD_EWS_TWILIO_FROM_NUMBER",
        "FLOOD_EWS_ALERT_SMS_TO",
    ))


def capabilities() -> dict[str, str]:
    return {
        "web": "available",
        "email": "available" if email_configured() else "not_configured",
        "sms": "available" if sms_configured() else "not_configured",
    }


def send_email(subject: str, message: str) -> str:
    if not email_configured():
        return "not_configured"
    payload = {
        "service_id": os.environ["FLOOD_EWS_EMAILJS_SERVICE_ID"].strip(),
        "template_id": os.environ["FLOOD_EWS_EMAILJS_ALERT_TEMPLATE_ID"].strip(),
        "user_id": os.environ["FLOOD_EWS_EMAILJS_PUBLIC_KEY"].strip(),
        "template_params": {
            "to_email": os.environ["FLOOD_EWS_ALERT_EMAIL_TO"].strip(),
            "subject": subject,
            "message": message,
        },
    }
    private_key = os.getenv("FLOOD_EWS_EMAILJS_PRIVATE_KEY", "").strip()
    if private_key:
        payload["accessToken"] = private_key
    try:
        status, _ = _post_json("https://api.emailjs.com/api/v1.0/email/send", payload)
        return "sent" if 200 <= status < 300 else "failed"
    except Exception:
        return "failed"


def send_sms(message: str) -> str:
    if not sms_configured():
        return "not_configured"
    sid = os.environ["FLOOD_EWS_TWILIO_ACCOUNT_SID"].strip()
    token = os.environ["FLOOD_EWS_TWILIO_AUTH_TOKEN"].strip()
    form = parse.urlencode({
        "From": os.environ["FLOOD_EWS_TWILIO_FROM_NUMBER"].strip(),
        "To": os.environ["FLOOD_EWS_ALERT_SMS_TO"].strip(),
        "Body": message,
    }).encode("utf-8")
    auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
    req = request.Request(
        f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
        data=form, method="POST",
        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with request.urlopen(req, timeout=10) as response:
            return "sent" if 200 <= response.status < 300 else "failed"
    except Exception:
        return "failed"


def dispatch(station_id: str, station_name: str, risk_level: str, message: str) -> dict[str, str]:
    subject = f"FloodWatch {risk_level} alert - {station_name} ({station_id})"
    return {"web": "available", "email": send_email(subject, message), "sms": send_sms(message)}
