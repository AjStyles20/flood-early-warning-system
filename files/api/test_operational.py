"""Isolated operational regression and failure-path tests (no live messages).

The temporary directory holds a real SQLite file and all test notification
logs. Nothing is written to the demonstration database or to a real provider.
"""
import csv
from datetime import datetime, timedelta
import io
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

TEST_RUNTIME = tempfile.TemporaryDirectory(prefix="floodwatch-operations-")
os.environ["FLOOD_EWS_DATABASE_URL"] = "sqlite:///" + (Path(TEST_RUNTIME.name) / "operations.db").as_posix()
os.environ["FLOOD_EWS_RUNTIME_DIR"] = TEST_RUNTIME.name
os.environ["FLOOD_EWS_INGEST_TOKEN"] = ""
os.environ["FLOOD_EWS_NEWS_PROVIDER"] = "off"
os.environ["FLOOD_EWS_BOOTSTRAP_ADMIN_EMAILS"] = "viewer@example.com"

from fastapi.testclient import TestClient
from pypdf import PdfReader
import main
import models
import news_feeds
from database import SessionLocal, engine
from manage_operator import assign_role


def reading(station="OP-01", source="simulated"):
    return dict(station_id=station, station_name="Portable test station", data_source=source,
                lat=7.8, lon=6.7, timestamp="2026-09-08T10:00:00Z", water_level_m=4.5,
                danger_level_m=5.0, rainfall_mm_hr=12, flow_rate_m3s=45,
                battery_pct=98, signal="online")


class OperationsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.guest = TestClient(main.app)
        cls.admin = TestClient(main.app)
        cls.operator = TestClient(main.app)
        cls.viewer = TestClient(main.app)
        cls.users = {}
        for role, client in (("admin", cls.admin), ("operator", cls.operator), ("viewer", cls.viewer)):
            response = client.post("/api/auth/register", json=dict(
                first_name="Test", last_name=role, email=f"{role}@example.com",
                phone_number="+2348000000000", password="IsolatedTestPass!42", role="admin"))
            assert response.status_code == 201, response.text
            assert response.json()["user"]["role"] == "user", "Signup must not grant supplied or bootstrap roles"
            cls.users[role] = response.json()["user"]["id"]
            if role != "viewer":
                with SessionLocal() as db:
                    assign_role(db, f"{role}@example.com", role)

    def test_alert_workflow_and_persistence(self):
        self.assertEqual(self.guest.post("/api/telemetry", json=reading()).status_code, 200)
        self.guest.post("/api/telemetry", json=reading())
        alerts = self.operator.get("/api/alerts").json()
        selected = [a for a in alerts if a["station_id"] == "OP-01"]
        self.assertEqual(len(selected), 1, "Repeated readings must not duplicate active alerts")
        alert_id = selected[0]["id"]
        url = f"/api/alerts/{alert_id}"
        self.assertEqual(self.guest.post(url + "/acknowledge", json={}).status_code, 401)
        self.assertEqual(self.viewer.post(url + "/acknowledge", json={}).status_code, 403)
        note = "Review <script>operator note</script>"
        for action, target in (("acknowledge", "acknowledged"), ("escalate", "escalated"), ("resolve", "resolved")):
            response = self.operator.post(url + "/" + action, json={"notes": note})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["status"], target)
            self.assertEqual(response.json()["channels"]["sms"], "simulated")
        self.assertEqual(self.operator.post(url + "/acknowledge", json={}).status_code, 409)
        self.assertEqual(self.operator.post(url + "/resolve", json={}).status_code, 409)
        audit = self.operator.get(url + "/audit").json()
        self.assertEqual([a["action"] for a in audit], ["acknowledge", "escalate", "resolve"])
        self.assertEqual(audit[-1]["notes"], note)
        public_alert = next(a for a in self.guest.get("/api/alerts").json() if a["id"] == alert_id)
        self.assertIsNone(public_alert["operator_notes"], "Private notes require an operator session")
        self.assertEqual(self.guest.get(url + "/audit").status_code, 401)
        self.assertEqual(self.viewer.get(url + "/audit").status_code, 403)
        self.assertEqual(self.operator.get("/api/alerts/987654/audit").status_code, 404)
        # A fresh process reads the durable audit from the same test file.
        result = subprocess.run([sys.executable, "-c", "from database import SessionLocal; from models import AlertAuditLog; db=SessionLocal(); print(db.query(AlertAuditLog).count()); db.close()"], cwd=Path(__file__).parent, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertGreaterEqual(int(result.stdout.strip()), 3)

    def test_roles_and_cross_origin_writes(self):
        self.assertEqual(self.viewer.get("/api/admin/users").status_code, 403)
        self.assertEqual(self.operator.get("/api/admin/users").status_code, 403)
        self.assertEqual(self.admin.get("/api/admin/users").status_code, 200)
        self.assertEqual(self.admin.patch(f"/api/admin/users/{self.users['admin']}/role", json={"role": "viewer"}).status_code, 409)
        endpoint = f"/api/admin/users/{self.users['viewer']}/role"
        self.assertEqual(self.viewer.patch(endpoint, json={"role": "admin"}).status_code, 403)
        self.assertEqual(self.admin.patch(endpoint, json={"role": "superuser"}).status_code, 422)
        for headers in ({"Origin": "https://attacker.example"}, {"Origin": "null"}, {"Sec-Fetch-Site": "cross-site"}):
            self.assertEqual(self.admin.patch(endpoint, json={"role": "admin"}, headers=headers).status_code, 403)
        self.assertEqual(self.admin.patch(endpoint, json={"role": "operator"}, headers={"Origin": "http://testserver"}).status_code, 200)
        self.assertEqual(self.viewer.get("/api/auth/me").json()["role"], "operator")
        self.admin.patch(endpoint, json={"role": "viewer"})

    def test_contact_public_configuration_and_template_safety(self):
        # These are deliberately fake IDs; rendering a page makes no provider
        # request. Even a mistaken environment value cannot escape Jinja JSON.
        public_key = '</script><script>alert("fixture")</script>'
        settings = {
            "FLOOD_EWS_EMAILJS_PUBLIC_KEY": public_key,
            "FLOOD_EWS_EMAILJS_SERVICE_ID": "service-fixture",
            "FLOOD_EWS_EMAILJS_CONTACT_TEMPLATE_ID": "template-fixture",
            "FLOOD_EWS_EMAILJS_PRIVATE_KEY": "private-fixture-do-not-render",
        }
        with patch.dict(os.environ, settings):
            response = self.guest.get("/contact")
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(public_key, response.text)
            self.assertNotIn(settings["FLOOD_EWS_EMAILJS_PRIVATE_KEY"], response.text)
            match = re.search(r'<script id="emailjs-config" type="application/json">(.*?)</script>', response.text, re.S)
            self.assertIsNotNone(match)
            self.assertEqual(json.loads(match.group(1)), {"publicKey": public_key, "serviceId": "service-fixture", "contactTemplateId": "template-fixture"})
            self.assertIn('aria-describedby="contact-delivery-info"', response.text)
            self.assertIn('role="status"', response.text)
            self.assertIn('method="post" action="/contact"', response.text)
            self.assertIn("sent through EmailJS", response.text)
        with patch.dict(os.environ, {name: "" for name in settings}), patch.object(main, "CONTACT_EMAIL", ""):
            response = self.guest.get("/contact")
            self.assertRegex(response.text, r'id="contact-submit"[^>]*disabled')
            self.assertIn("contact service is not connected", response.text)

    def test_session_expiry_revocation_and_cookie_flags(self):
        client = TestClient(main.app)
        with patch.object(main, "SECURE_SESSION_COOKIES", True):
            response = client.post("/api/auth/login", json={"email": "viewer@example.com", "password": "IsolatedTestPass!42"})
        cookie = response.headers["set-cookie"].lower()
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=lax", cookie)
        self.assertIn("secure", cookie)
        self.assertEqual(response.headers["cache-control"], "no-store")
        token = response.json()["access_token"]
        with SessionLocal() as db:
            session = db.query(models.UserSession).filter_by(token_hash=main.hash_token(token)).one()
            self.assertNotEqual(session.token_hash, token)
            session.expires_at = datetime.utcnow() - timedelta(seconds=1)
            db.commit()
        self.assertEqual(self.guest.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code, 401)
        client = TestClient(main.app)
        login = client.post("/api/auth/login", json={"email": "viewer@example.com", "password": "IsolatedTestPass!42"})
        token = login.json()["access_token"]
        self.assertEqual(client.get("/logout").status_code, 405)
        self.assertEqual(client.post("/logout", follow_redirects=False).status_code, 303)
        self.assertEqual(self.guest.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code, 401)

    def test_csv_validation_provenance_and_auth(self):
        data = reading("CSV-01", "hardware")
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=list(data))
        writer.writeheader()
        writer.writerow(data)
        writer.writerow({**data, "danger_level_m": 0})
        writer.writerow({**data, "water_level_m": "inf"})
        # Overfull rows used to raise AttributeError on DictReader's list value.
        contents = output.getvalue() + ",".join(str(v) for v in data.values()) + ",unexpected
"
        url = "/api/telemetry/upload-csv"
        files = {"file": ("evidence.csv", contents.encode(), "text/csv")}
        self.assertEqual(self.guest.post(url, files=files).status_code, 401)
        self.assertEqual(self.viewer.post(url, files=files).status_code, 403)
        response = self.operator.post(url, files=files)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual((response.json()["accepted"], response.json()["rejected"]), (1, 3))
        rows = self.guest.get("/api/telemetry?data_source=hardware").json()
        self.assertTrue(any(row["station_id"] == "CSV-01" for row in rows))
        for name, content, expected in (("a.txt", b"abc", 422), ("a.csv", b"x,y
1,2", 422), ("a.csv", b"\xff", 422), ("a.csv", b"x" * 2_000_001, 413)):
            self.assertEqual(self.operator.post(url, files={"file": (name, content)}).status_code, expected)
        self.assertEqual(self.guest.get("/api/telemetry?limit=-1").status_code, 422)
        malformed = ','.join(data) + '
"unclosed quote'
        self.assertEqual(self.operator.post(url, files={"file": ("malformed.csv", malformed.encode())}).status_code, 422)
        oversized_field = ','.join(data) + '
' + 'x' * 140000
        self.assertEqual(self.operator.post(url, files={"file": ("large-field.csv", oversized_field.encode())}).status_code, 422)

    def test_ingest_key_and_sensor_validation(self):
        with patch.object(main, "INGEST_TOKEN", "isolated-ingest-secret"):
            self.assertEqual(self.guest.post("/api/telemetry", json=reading()).status_code, 401)
            self.assertEqual(self.guest.post("/api/telemetry", json=reading(), headers={"X-Ingest-Token": "wrong"}).status_code, 401)
            self.assertEqual(self.guest.post("/api/telemetry", json=reading(), headers={"X-Ingest-Token": "isolated-ingest-secret"}).status_code, 200)
        self.assertEqual(self.guest.post("/api/telemetry", json={**reading(), "station_id": "   "}).status_code, 422)

    def test_scenario_reports_and_pdf_completeness(self):
        self.guest.post("/api/telemetry", json=reading("SCENARIO-01", "hardware"))
        payload = {"station_id": "SCENARIO-01", "scenario": "normal"}
        self.assertEqual(self.guest.post("/api/scenario/run", json=payload).status_code, 401)
        self.assertEqual(self.viewer.post("/api/scenario/run", json=payload).status_code, 403)
        response = self.operator.post("/api/scenario/run", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        run = response.json()["scenario_run"]
        self.assertLess(run["after_water_level_m"], run["before_water_level_m"])
        url = f"/api/scenario-runs/{run['id']}/report.pdf"
        self.assertEqual(self.guest.get(url).status_code, 401)
        self.assertEqual(self.operator.get("/api/scenario-runs/987654/report.pdf").status_code, 404)
        document = self.operator.get(url)
        extracted = " ".join(page.extract_text() for page in PdfReader(io.BytesIO(document.content)).pages)
        self.assertIn("Saved holdout evaluation snapshot", extracted)
        self.assertIn("FP=", extracted)
        self.assertIn("FN=", extracted)
        self.assertEqual(self.guest.get("/api/model-evaluation/report.pdf").status_code, 401)
        model_pdf = self.operator.get("/api/model-evaluation/report.pdf")
        self.assertEqual(model_pdf.status_code, 200)
        text = " ".join(page.extract_text() for page in PdfReader(io.BytesIO(model_pdf.content)).pages)
        self.assertIn("FP=", text)
        self.assertIn("FN=", text)
        long_pdf = main.simple_pdf("Pagination test", ["Complete line " + str(i) for i in range(120)])
        reader = PdfReader(io.BytesIO(long_pdf))
        self.assertGreater(len(reader.pages), 1)
        self.assertIn("Complete line 119", reader.pages[-1].extract_text())
        self.assertEqual(self.guest.get("/api/model-evaluation").status_code, 401)
        metrics = self.operator.get("/api/model-evaluation").json()
        for result in metrics["results"].values():
            total = sum(result[key] for key in ("true_positive", "true_negative", "false_positive", "false_negative"))
            self.assertEqual(total, metrics["test_samples"])
            self.assertAlmostEqual(result["accuracy"], (result["true_positive"] + result["true_negative"]) / total)

    def test_health_success_and_database_failure(self):
        self.assertEqual(self.guest.get("/health").status_code, 200)
        class UnavailableDatabase:
            def execute(self, statement):
                raise RuntimeError("Simulated unavailable database")
        main.app.dependency_overrides[main.get_db] = lambda: UnavailableDatabase()
        try:
            response = self.guest.get("/health")
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["database"], "unavailable")
        finally:
            main.app.dependency_overrides.clear()


class NewsTest(unittest.TestCase):
    def setUp(self):
        news_feeds._CACHE.clear()

    def test_unconfigured_and_off_modes(self):
        with patch.dict(os.environ, {"FLOOD_EWS_NEWS_PROVIDER": "newsapi", "FLOOD_EWS_NEWSAPI_KEY": ""}):
            self.assertFalse(news_feeds.fetch_news()["configured"])
        with patch.dict(os.environ, {"FLOOD_EWS_NEWS_PROVIDER": "off"}):
            self.assertFalse(news_feeds.fetch_news()["configured"])

    def test_article_links_rss_dates_and_cache(self):
        xml = '<rss><channel><title>Institution</title><item><title>Flood update</title><link>https://example.org/flood</link><pubDate>Tue, 08 Sep 2026 09:00:00 GMT</pubDate></item><item><title>Unsafe</title><link>javascript:alert(1)</link></item></channel></rss>'
        with patch.dict(os.environ, {"FLOOD_EWS_NEWS_PROVIDER": "rss", "FLOOD_EWS_RSS_FEEDS": "https://example.org/rss"}), patch.object(news_feeds, "_http_text", return_value=xml) as fetch:
            payload = news_feeds.fetch_news(limit=2)
            self.assertEqual(len(payload["articles"]), 1)
            self.assertIsNotNone(payload["articles"][0]["published_at"].tzinfo)
            news_feeds.fetch_news(limit=2, force_refresh=True)
            self.assertEqual(fetch.call_count, 1)
            news_feeds.fetch_news(limit=1)
            self.assertEqual(fetch.call_count, 2)
        self.assertEqual(news_feeds.safe_article_url("file:///etc/passwd"), "")
        self.assertEqual(news_feeds.safe_article_url("https://name:secret@example.org"), "")

    def test_provider_failures_hide_keys(self):
        with patch.dict(os.environ, {"FLOOD_EWS_NEWS_PROVIDER": "gnews", "FLOOD_EWS_GNEWS_API_KEY": "DO-NOT-EXPOSE"}), patch.object(news_feeds, "_http_json", side_effect=RuntimeError("https://example.org?apikey=DO-NOT-EXPOSE")):
            payload = news_feeds.fetch_news()
            self.assertTrue(payload["configured"])
            self.assertEqual(payload["articles"], [])
            self.assertNotIn("DO-NOT-EXPOSE", json.dumps(payload, default=str))

    def test_newsapi_and_gnews_use_header_credentials(self):
        for provider, variable in (("newsapi", "FLOOD_EWS_NEWSAPI_KEY"), ("gnews", "FLOOD_EWS_GNEWS_API_KEY")):
            with patch.dict(os.environ, {"FLOOD_EWS_NEWS_PROVIDER": provider, variable: "test-key"}), patch.object(news_feeds, "_http_json", return_value={"articles": []}) as fetch:
                payload = news_feeds.fetch_news()
                self.assertTrue(payload["configured"])
                self.assertNotIn("test-key", fetch.call_args.args[0])
                self.assertEqual(fetch.call_args.kwargs["headers"]["X-Api-Key"], "test-key")


if __name__ == "__main__":
    try:
        unittest.main(verbosity=2)
    finally:
        engine.dispose()
        TEST_RUNTIME.cleanup()
