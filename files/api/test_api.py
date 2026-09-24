"""Executable verification for the approved FloodWatch core and parked extras.

The tests are written in plain sections so they can be explained during a
defense: send a request, read the response, and check that unsafe or
out-of-scope behaviour is rejected.
"""

import os
import re
import tempfile
from pathlib import Path

# Use an isolated *file-based* SQLite database for tests. This preserves the
# project guardrail that SQLite should be used as a real file, not as the
# accidental in-memory ``sqlite://`` URL that previously caused persistence bugs.
TEST_RUNTIME = tempfile.TemporaryDirectory(prefix="floodwatch-api-test-")
TEST_DATABASE_PATH = Path(TEST_RUNTIME.name) / "test_flood_data.db"
os.environ["FLOOD_EWS_DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"
os.environ["FLOOD_EWS_RUNTIME_DIR"] = TEST_RUNTIME.name
os.environ["FLOOD_EWS_INGEST_TOKEN"] = ""

from fastapi.testclient import TestClient

import models
from database import Base, DEFAULT_DATABASE_URL, SessionLocal, engine
from main import ENABLE_COMMUNITY_REPORTS, PENDING_ACCOUNT_DELETIONS, PENDING_REGISTRATIONS, app, get_db
from risk_engine import classify


TestingSessionLocal = SessionLocal
Base.metadata.create_all(bind=engine)


def override_get_db():
    """Give each request a database session attached to the test engine."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)
anonymous_client = TestClient(app)
form_client = TestClient(app)
extra_client = TestClient(app)


def check(condition, message):
    """Raise a useful assertion instead of printing a misleading pass message."""
    if not condition:
        raise AssertionError(message)


def extract_pending_token(html: str) -> str:
    """Read the short-lived confirmation token from the account-preview form."""
    match = re.search(r'name="pending_token" value="([^"]+)"', html)
    if not match:
        raise AssertionError("The confirmation page must include a pending registration token.")
    return match.group(1)


def extract_deletion_token(html: str) -> str:
    """Read the short-lived deletion token from the account-delete verification form."""
    match = re.search(r'name="deletion_token" value="([^"]+)"', html)
    if not match:
        raise AssertionError("The deletion verification page must include a deletion token.")
    return match.group(1)


def extract_deletion_code(html: str) -> str:
    """Read the simulated local verification code shown for the defense demo."""
    match = re.search(r'<code>([0-9]{6})</code>', html)
    if not match:
        raise AssertionError("The deletion verification page must show a six-digit demo code.")
    return match.group(1)


print("\n>>> STARTING FLOODWATCH CORE + SCOPE GUARD TEST...")
print("-" * 68)

simulated_payload = {
    "station_id": "STN-01",
    "station_name": "Lokoja Sensor (Virtual Test)",
    "data_source": "simulated",
    "lat": 7.79,
    "lon": 6.73,
    "timestamp": "2026-08-26T12:00:00Z",
    "water_level_m": 4.5,
    "danger_level_m": 5.5,
    "rainfall_mm_hr": 12.0,
    "flow_rate_m3s": 45.0,
    "battery_pct": 98.5,
    "signal": "online",
}

hardware_payload = {
    **simulated_payload,
    "data_source": "hardware",
    "timestamp": "2026-08-26T12:01:00Z",
    "water_level_m": 5.7,
}

print("1. SENSOR INGESTION:")
simulated_response = client.post("/api/telemetry", json=simulated_payload)
hardware_response = client.post("/api/telemetry", json=hardware_payload)
print(f"   simulated status: {simulated_response.status_code}, source: {simulated_response.json().get('data_source')}")
print(f"   hardware status:  {hardware_response.status_code}, source: {hardware_response.json().get('data_source')}\n")
check(simulated_response.status_code == 200, "Simulated telemetry POST must succeed.")
check(hardware_response.status_code == 200, "Hardware telemetry POST must succeed.")
check(simulated_response.json()["data_source"] == "simulated", "Simulated provenance must be stored.")
check(hardware_response.json()["data_source"] == "hardware", "Hardware provenance must be stored.")

print("2. BREAK TESTS FOR BAD SENSOR/API INPUT:")
bad_source = client.post("/api/telemetry", json={**simulated_payload, "data_source": "manual"})
bad_latitude = client.post("/api/telemetry", json={**simulated_payload, "lat": 120})
bad_danger_level = client.post("/api/telemetry", json={**simulated_payload, "danger_level_m": 0})
bad_battery = client.post("/api/telemetry", json={**simulated_payload, "battery_pct": 150})
missing_station = client.post("/api/telemetry", json={key: value for key, value in simulated_payload.items() if key != "station_id"})
print(f"   rejected source:       {bad_source.status_code}")
print(f"   rejected latitude:     {bad_latitude.status_code}")
print(f"   rejected danger level: {bad_danger_level.status_code}")
print(f"   rejected battery:      {bad_battery.status_code}")
print(f"   rejected missing ID:   {missing_station.status_code}\n")
check(bad_source.status_code == 422, "Unknown data_source values must be rejected.")
check(bad_latitude.status_code == 422, "Latitude outside -90..90 must be rejected.")
check(bad_danger_level.status_code == 422, "Zero danger level must be rejected before risk division.")
check(bad_battery.status_code == 422, "Battery above 100 percent must be rejected.")
check(missing_station.status_code == 422, "Missing station_id must be rejected.")

print("3. CORE DASHBOARD AND DATA ACCESS WITHOUT ACCOUNT DEPENDENCY:")
public_risk = anonymous_client.get("/api/risk-status")
public_telemetry = anonymous_client.get("/api/telemetry")
hardware_telemetry = anonymous_client.get("/api/telemetry", params={"data_source": "hardware"})
invalid_telemetry_source = anonymous_client.get("/api/telemetry", params={"data_source": "manual"})
public_dashboard = anonymous_client.get("/dashboard")
public_data_page = anonymous_client.get("/data")
print(f"   public risk API:      {public_risk.status_code}")
print(f"   public telemetry API: {public_telemetry.status_code}, rows: {len(public_telemetry.json())}")
print(f"   hardware filter:     {hardware_telemetry.status_code}, rows: {len(hardware_telemetry.json())}")
print(f"   invalid filter:      {invalid_telemetry_source.status_code}")
print(f"   public dashboard:     {public_dashboard.status_code}")
print(f"   public data page:     {public_data_page.status_code}\n")
check(public_risk.status_code == 200, "Core risk-status API must support the dashboard without account gating.")
check(public_telemetry.status_code == 200, "Core telemetry API must support the data page without account gating.")
check(len(public_telemetry.json()) == 2, "Telemetry GET must return saved simulated and hardware readings.")
check(hardware_telemetry.status_code == 200, "Telemetry source filter must accept hardware.")
check(len(hardware_telemetry.json()) == 1, "Hardware telemetry filter must return only hardware readings.")
check(hardware_telemetry.json()[0]["data_source"] == "hardware", "Hardware telemetry filter must preserve source provenance.")
check(invalid_telemetry_source.status_code == 422, "Telemetry source filter must reject unsupported source names.")
check(public_dashboard.status_code == 200, "Core dashboard page must render without login.")
check(public_data_page.status_code == 200, "Core data page must render without login.")

print("4. OPTIONAL ACCOUNT SHELL STILL WORKS, BUT COMMUNITY REPORTING IS PARKED:")
register_response = client.post(
    "/api/auth/register",
    json={
        "first_name": "Ada",
        "last_name": "Okafor",
        "email": "ada@example.com",
        "phone_number": "+2348012345678",
        "password": "StrongPass123!",
    },
)
duplicate_register = client.post(
    "/api/auth/register",
    json={
        "first_name": "Ada",
        "last_name": "Okafor",
        "email": "ada@example.com",
        "phone_number": "+2348012345678",
        "password": "StrongPass123!",
    },
)
weak_register = client.post(
    "/api/auth/register",
    json={
        "first_name": "Weak",
        "last_name": "User",
        "email": "weak@example.com",
        "phone_number": "+2348012345678",
        "password": "short",
    },
)
login_response = client.post(
    "/api/auth/login",
    json={"email": "ada@example.com", "password": "StrongPass123!"},
)
bad_login_response = client.post(
    "/api/auth/login",
    json={"email": "ada@example.com", "password": "wrong-password"},
)
anonymous_settings_post = anonymous_client.post(
    "/settings/report",
    data={"title": "Blocked", "location": "Nowhere", "message": "No session should post this."},
)
headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
parked_report_post = client.post(
    "/settings/report",
    data={"title": "Parked", "location": "Abuja", "message": "This feature should be disabled by default."},
    headers=headers,
)
print(f"   register:              {register_response.status_code}")
print(f"   duplicate register:    {duplicate_register.status_code}")
print(f"   weak password:         {weak_register.status_code}")
print(f"   login:                 {login_response.status_code}, token present: {'access_token' in login_response.json()}")
print(f"   bad login:             {bad_login_response.status_code}")
print(f"   anonymous report POST: {anonymous_settings_post.status_code}")
print(f"   parked report POST:    {parked_report_post.status_code}, enabled flag: {ENABLE_COMMUNITY_REPORTS}\n")
check(register_response.status_code == 201, "Optional account shell registration must still work.")
check(duplicate_register.status_code == 409, "Duplicate email registration must be rejected.")
check(weak_register.status_code == 422, "Too-short passwords must be rejected.")
check(login_response.status_code == 200, "Login must succeed for a registered user.")
check("access_token" in login_response.json(), "Login must return an account access token.")
check(bad_login_response.status_code == 401, "Incorrect password must be rejected.")
check(anonymous_settings_post.status_code == 401, "Anonymous users must not post parked extras.")
check(parked_report_post.status_code == 403, "Community reporting must be parked by default.")

# Privilege is granted from a trusted server context, never from signup input.
from manage_operator import assign_role
with TestingSessionLocal() as db:
    check(db.get(models.User, register_response.json()["user"]["id"]).role == "user", "Public registration must never grant admin access.")
    assign_role(db, "ada@example.com", "admin")

print("5. JINJA2 PAGE ROUTING:")
home_page = anonymous_client.get("/")
about_page = anonymous_client.get("/about")
projects_page = anonymous_client.get("/projects")
news_page = anonymous_client.get("/news")
contact_page = anonymous_client.get("/contact")
login_page = anonymous_client.get("/login")
register_page = anonymous_client.get("/register")
favicon_response = anonymous_client.get("/favicon.ico")
legacy_page = anonymous_client.get("/dashboard/pages/home/index.html", follow_redirects=False)
signed_in_dashboard = client.get("/dashboard")
print(f"   public home:          {home_page.status_code}")
print(f"   public about:         {about_page.status_code}")
print(f"   public projects:      {projects_page.status_code}")
print(f"   public news:          {news_page.status_code}")
print(f"   public contact:       {contact_page.status_code}")
print(f"   login/register:       {login_page.status_code}/{register_page.status_code}")
print(f"   favicon:              {favicon_response.status_code}")
print(f"   legacy static route:  {legacy_page.status_code} -> {legacy_page.headers.get('location')}")
print(f"   signed-in dashboard:  {signed_in_dashboard.status_code}\n")
check(home_page.status_code == 200, "Public Jinja2 home page must render.")
check("Flood intelligence" in home_page.text, "Home page must contain the public welcome content.")
check(about_page.status_code == 200, "About page must render.")
check(projects_page.status_code == 200, "Projects page must render.")
check(news_page.status_code == 200, "News page must render.")
check(contact_page.status_code == 200, "Contact page must render.")
check(login_page.status_code == 200, "Login page must render.")
check(register_page.status_code == 200, "Register page must render.")
check(favicon_response.status_code == 200, "Browser favicon requests must not produce 404 demo noise.")
check("image/svg+xml" in favicon_response.headers.get("content-type", ""), "Favicon route must serve an SVG icon.")
check('rel="icon"' in home_page.text, "Base template must advertise a browser favicon.")
check(legacy_page.status_code == 307, "Old static prototype routes must redirect away.")
check(signed_in_dashboard.status_code == 200, "Logged-in dashboard page must still render.")
check("National situation room" in signed_in_dashboard.text, "Dashboard must render the command-centre content.")
check('id="time-aware-greeting"' in signed_in_dashboard.text, "Dashboard greeting must expose a time-aware greeting span.")
check("risk-zone-toggle" in signed_in_dashboard.text, "Dashboard must expose a risk-ring map control.")
check("station-label-toggle" in signed_in_dashboard.text, "Dashboard must expose a station-label map control.")
check("station-search" in signed_in_dashboard.text, "Dashboard must expose station search for the map/list.")
check("risk-filter" in signed_in_dashboard.text, "Dashboard must expose risk-level filtering.")
check("map-health" in signed_in_dashboard.text, "Dashboard must expose map tile-health feedback.")
check("selected-station-panel" in signed_in_dashboard.text, "Dashboard must expose a selected-station detail panel.")
check("corridor-toggle" in signed_in_dashboard.text, "Dashboard must expose a schematic river-context toggle.")
check("aria-describedby=\"map-instructions map-summary\"" in signed_in_dashboard.text, "Map must describe its text alternative for accessibility.")

print("6. HTML REGISTRATION CONFIRMATION, HOME REDIRECT, SETTINGS, AND DELETE CODE GUARDS:")
unaccepted_terms = form_client.post(
    "/register",
    data={
        "first_name": "Grace",
        "last_name": "Ibrahim",
        "email": "grace@example.com",
        "phone_number": "+2348099990000",
        "password": "abc123def456",
        "next_path": "/settings",
    },
)
missing_phone_preview = form_client.post(
    "/register",
    data={
        "first_name": "Grace",
        "last_name": "Ibrahim",
        "email": "missing-phone@example.com",
        "password": "abc123def456",
        "terms_accepted": "yes",
    },
)
preview_response = form_client.post(
    "/register",
    data={
        "first_name": "Grace",
        "last_name": "Ibrahim",
        "email": "grace@example.com",
        "phone_number": "+2348099990000",
        "password": "abc123def456",
        "next_path": "/settings",
        "terms_accepted": "yes",
    },
)
preconfirm_login = anonymous_client.post(
    "/api/auth/login",
    json={"email": "grace@example.com", "password": "abc123def456"},
)
pending_token = extract_pending_token(preview_response.text)
pending_created = pending_token in PENDING_REGISTRATIONS
confirm_response = form_client.post(
    "/register",
    data={"pending_token": pending_token, "confirm": "yes", "next_path": "/settings"},
    follow_redirects=False,
)
logged_in_home = form_client.get("/")
settings_page = form_client.get("/settings")
profile_update = form_client.post(
    "/settings/profile",
    data={
        "first_name": "Grace",
        "last_name": "Ibrahim-Updated",
        "phone_number": "+2348099990001",
        "email_updates": "yes",
        "sms_updates": "yes",
        "whatsapp_updates": "yes",
    },
    follow_redirects=False,
)
bad_profile_update = form_client.post(
    "/settings/profile",
    data={"first_name": "   ", "last_name": "   ", "phone_number": "+2348099990001"},
)
delete_request = form_client.post(
    "/settings/delete/request",
    data={"delete_reason": "bug_or_issue", "delete_feedback": "Testing the verification flow."},
)
delete_token = extract_deletion_token(delete_request.text)
delete_code = extract_deletion_code(delete_request.text)
pending_delete_created = delete_token in PENDING_ACCOUNT_DELETIONS
wrong_code_delete = form_client.post(
    "/settings/delete",
    data={"deletion_token": delete_token, "verification_code": "000000", "confirm_delete": "DELETE"},
)
bad_delete = form_client.post(
    "/settings/delete",
    data={"deletion_token": delete_token, "verification_code": delete_code, "confirm_delete": "delete"},
)
good_delete = form_client.post(
    "/settings/delete",
    data={"deletion_token": delete_token, "verification_code": delete_code, "confirm_delete": "DELETE"},
    follow_redirects=False,
)
deleted_home = form_client.get("/?account_deleted=1")
settings_after_delete = form_client.get("/settings", follow_redirects=False)
print(f"   register without terms: {unaccepted_terms.status_code}")
print(f"   missing phone preview:  {missing_phone_preview.status_code}")
print(f"   preview page:           {preview_response.status_code}")
print(f"   login before confirm:   {preconfirm_login.status_code}")
print(f"   confirm account:        {confirm_response.status_code} -> {confirm_response.headers.get('location')}")
print(f"   logged-in home:         {logged_in_home.status_code}")
print(f"   settings page:          {settings_page.status_code}")
print(f"   profile update:         {profile_update.status_code}")
print(f"   bad profile update:     {bad_profile_update.status_code}")
print(f"   delete code request:    {delete_request.status_code}, pending: {pending_delete_created}")
print(f"   wrong delete code:      {wrong_code_delete.status_code}")
print(f"   guarded delete typo:    {bad_delete.status_code}")
print(f"   confirmed delete:       {good_delete.status_code} -> {good_delete.headers.get('location')}")
print(f"   settings after delete:  {settings_after_delete.status_code} -> {settings_after_delete.headers.get('location')}\n")
check(unaccepted_terms.status_code == 422, "HTML registration must require terms acceptance before preview.")
check(missing_phone_preview.status_code == 422, "HTML registration must require a phone number for SMS-capable contact.")
check(preview_response.status_code == 200, "First HTML registration step must show a confirmation page.")
check("Confirm your account details" in preview_response.text, "Preview page must ask users to confirm inputs.")
check("+2348099990000" in preview_response.text, "Preview page must include the phone number the user is confirming.")
check("abc123def456" not in preview_response.text, "Preview page must not expose the raw password.")
check(pending_created, "Preview step must create a temporary pending registration.")
check(preconfirm_login.status_code == 401, "The account must not exist before the confirmation step.")
check(confirm_response.status_code == 303, "Confirming the preview must create the account and redirect.")
check(confirm_response.headers["location"] == "/", "Confirmed registration must send users to the home page.")
check(pending_token not in PENDING_REGISTRATIONS, "Pending registration token must be removed after account creation.")
check(logged_in_home.status_code == 200, "Logged-in home page must render after account confirmation.")
check("Continue as guest" not in logged_in_home.text, "Logged-in users must not be invited to continue as guest.")
check("Account settings" in logged_in_home.text, "Logged-in home page should offer account settings instead of account creation.")
check(settings_page.status_code == 200, "Logged-in settings page must render.")
check("Community reporting parked" in settings_page.text, "Settings must clearly mark community reporting as parked.")
check("Create account" not in settings_page.text and "Log in" not in settings_page.text, "Logged-in footer must not repeat login/register links.")
check("Phone number for SMS-capable contact" in settings_page.text, "Settings must expose phone/SMS contact preferences.")
check("Send deletion verification code" in settings_page.text, "Settings must use a deletion verification-code step.")
check(profile_update.status_code == 303, "Profile/settings update must redirect after success.")
check(bad_profile_update.status_code == 422, "Blank profile names must be rejected.")
check(delete_request.status_code == 200, "Deletion request must render the verification-code step.")
check(pending_delete_created, "Deletion request must create a temporary pending deletion token.")
check("We are sorry you have to go" in delete_request.text, "Deletion flow must acknowledge the user before destructive confirmation.")
check("Local demo verification code" in delete_request.text, "Deletion flow must show the simulated local demo code.")
check(wrong_code_delete.status_code == 400, "Wrong deletion verification code must be rejected.")
check(bad_delete.status_code == 400, "Account delete typo must be rejected even with the right code.")
check(good_delete.status_code == 303 and good_delete.headers["location"] == "/?account_deleted=1", "Exact delete confirmation plus verification code must remove only the logged-in test account.")
check(delete_token not in PENDING_ACCOUNT_DELETIONS, "Pending deletion token must be consumed after deletion.")
check("Your account has been deleted" in deleted_home.text, "Home page must confirm account deletion after redirect.")
check(settings_after_delete.status_code == 303, "Deleted account must lose access to settings.")

print("7. RISK STATUS, SOURCE SWITCHING, AND INVALID QUERIES:")
simulated_risk = client.get("/api/risk-status", params={"data_source": "simulated"})
hardware_risk = client.get("/api/risk-status", params={"data_source": "hardware"})
hybrid_risk = client.get("/api/risk-status", params={"data_source": "hybrid"})
invalid_source_query = client.get("/api/risk-status", params={"data_source": "manual"})
invalid_language_query = client.get("/api/risk-status", params={"language": "xx"})
print(f"   simulated:        {simulated_risk.status_code}, {simulated_risk.json()[0]['risk_level']}")
print(f"   hardware:         {hardware_risk.status_code}, {hardware_risk.json()[0]['risk_level']}")
print(f"   hybrid:           {hybrid_risk.status_code}, {hybrid_risk.json()[0]['risk_level']} from {hybrid_risk.json()[0]['data_source']}")
print(f"   invalid source:   {invalid_source_query.status_code}")
print(f"   invalid language: {invalid_language_query.status_code}\n")
check(simulated_risk.status_code == 200, "Simulated risk-status endpoint must succeed.")
check(hardware_risk.status_code == 200, "Hardware risk-status endpoint must succeed.")
check(hybrid_risk.status_code == 200, "Hybrid risk-status endpoint must succeed.")
check(invalid_source_query.status_code == 422, "Unsupported source query must be rejected.")
check(invalid_language_query.status_code == 422, "Unsupported language query must be rejected.")
check(simulated_risk.json()[0]["risk_level"] == "High", "4.5m / 5.5m must be classified as High.")
check(hardware_risk.json()[0]["risk_level"] == "Severe", "5.7m / 5.5m must be classified as Severe.")
check(hybrid_risk.json()[0]["risk_level"] == "Severe", "Hybrid mode must choose the more serious current source.")
check(hybrid_risk.json()[0]["data_source"] == "hardware", "Hybrid mode must preserve selected source provenance.")
check(set(hybrid_risk.json()[0]["alert_channels"]) == {"web", "email", "sms"}, "Status must expose only approved active alert channels.")
check(hybrid_risk.json()[0]["message"].endswith("follow official guidance."), "English risk guidance must retain its safety wording.")
check("rainfall_mm_hr" in hybrid_risk.json()[0], "Risk-status payload must include rainfall for richer map popups.")
check("flow_rate_m3s" in hybrid_risk.json()[0], "Risk-status payload must include flow rate for richer map popups.")
check("battery_pct" in hybrid_risk.json()[0], "Risk-status payload must include battery state for station context.")
check("signal" in hybrid_risk.json()[0], "Risk-status payload must include signal state for station context.")
check("rate_of_rise_m" in hybrid_risk.json()[0], "Risk-status payload must expose measured rate of rise instead of forcing the UI to invent a trend.")

alerts_response = client.get("/api/alerts?limit=2")
check(alerts_response.status_code == 200, "Recent-alert endpoint must render without leaking FastAPI Query objects into internal calls.")
alert_log_response = client.post("/api/alerts/dispatch", json={"station_id": hybrid_risk.json()[0]["station_id"]})
check(alert_log_response.status_code == 200, "Simulated alert-log endpoint must accept a station ID.")
alert_event = alert_log_response.json()["event"]
check(set(alert_event["channels"].keys()) == {"web", "email", "sms"}, "Alert logs must stay on web/email/SMS simulation channels only.")
check(set(alert_event["channels"].values()) <= {"available", "not_configured", "sent", "failed"}, "Alert logs must expose only real provider capability/attempt outcomes.")
check("follow official guidance." in alert_event["message"], "Alert logs must preserve official-guidance safety wording.")
check("dispatched" not in alert_event["message"].lower() and "broadcast" not in alert_event["message"].lower(), "Alert logs must not use autonomous dispatch/broadcast language.")
missing_alert_target = client.post("/api/alerts/dispatch", json={"station_id": "UNKNOWN-STATION"})
missing_alert_id = client.post("/api/alerts/dispatch", json={})
missing_scenario_target = client.post("/api/scenario/run", json={"station_id": "UNKNOWN-STATION", "scenario": "flood"})
invalid_scenario = client.post("/api/scenario/run", json={"station_id": hybrid_risk.json()[0]["station_id"], "scenario": "storm"})
check(missing_alert_target.status_code == 404, "Alert simulation must not invent a fake station when telemetry is missing.")
check(missing_alert_id.status_code == 422, "Alert simulation must require a station_id.")
check(missing_scenario_target.status_code == 404, "Scenario runner must not create a hardcoded fallback station.")
check(invalid_scenario.status_code == 422, "Scenario runner must reject unsupported scenario names.")

print("8. RISK ENGINE BOUNDARIES, UI XSS GUARDS, AND DATABASE CONFIG:")
check(classify(1.0, 5.0).risk_level == "Low", "Low tier failed.")
check(classify(3.0, 5.0).risk_level == "Moderate", "Moderate tier failed.")
check(classify(4.0, 5.0).risk_level == "High", "High tier failed.")
check(classify(5.0, 5.0).risk_level == "Severe", "Severe tier failed.")
try:
    classify(1.0, 0.0)
    raise AssertionError("A zero danger level must be rejected.")
except ValueError:
    pass
with open("static/js/dashboard.js", encoding="utf-8") as dashboard_js:
    dashboard_script = dashboard_js.read()
with open("static/js/data.js", encoding="utf-8") as data_js:
    data_script = data_js.read()
with open("main.py", encoding="utf-8") as main_py:
    main_script = main_py.read()
with open("templates/base.html", encoding="utf-8") as base_html:
    base_template = base_html.read()
with open("static/css/site.css", encoding="utf-8") as site_css:
    site_styles = site_css.read()
with open("static/js/site.js", encoding="utf-8") as site_js:
    site_script = site_js.read()
with open("static/js/contact.js", encoding="utf-8") as contact_js:
    contact_script = contact_js.read()
with open("query_api.py", encoding="utf-8") as query_api_py:
    query_api_script = query_api_py.read()
check("function escapeHtml" in dashboard_script, "Dashboard station rendering must escape user/sensor text.")
check("estimateRiskRingRadius" in dashboard_script, "Dashboard map must render risk-ring planning overlays.")
check("data-focus-station" in dashboard_script, "Accessible station cards must be able to focus map markers.")
check("markersByStationId" in dashboard_script, "Map script must keep marker lookup for station-list keyboard control.")
check("filterStations" in dashboard_script, "Dashboard map must support station search/risk filtering.")
check("watchTileHealth" in dashboard_script, "Dashboard map must warn users if map tiles are unavailable.")
check("freshnessMeta" in dashboard_script, "Dashboard map must label stale or fresh station readings.")
check("function greetingForHour" in dashboard_script, "Dashboard must map local system hour to greeting text.")
check("updateTimeAwareGreeting" in dashboard_script, "Dashboard must update the greeting from the browser clock.")
check("60 * 1000" in dashboard_script, "Dashboard greeting must keep syncing while the page stays open.")
check("function formatSignedMetres" in dashboard_script, "Dashboard must render measured water-level trend from rate_of_rise_m.")
check("estimateLeadTimeLabel" in dashboard_script, "Dashboard lead-time display must be estimated from telemetry trend, not fixed clock values.")
check("sourceModeMeta" in dashboard_script and "source-mode-title" in signed_in_dashboard.text, "Dashboard must visibly explain Hybrid, Simulation, and Hardware telemetry modes.")
check("modelAvailabilitySummary" in dashboard_script, "Dashboard model status must be computed from model availability in API data.")
check("renderSelectedStationPanel" in dashboard_script, "Dashboard must render selected-station details beside the map.")
check("selectStation" in dashboard_script, "Map marker clicks and station-list buttons must update selected station state.")
check("riverCorridors" in dashboard_script, "Dashboard map must define schematic river corridor context.")
check("renderContextLayer" in dashboard_script, "Dashboard map must render the river corridor context layer.")
check("not an official flood boundary" in dashboard_script, "River context layer must avoid claiming official flood-boundary authority.")
check("Â" not in dashboard_script, "Dashboard JavaScript must not contain mojibake characters.")
check('aria-haspopup="dialog"' in base_template, "Notification bell must expose dialog semantics for assistive technology.")
check("notification-dropdown-header" in base_template, "Notification dropdown must render a readable heading and summary.")
check("z-index: 3200" in site_styles, "Notification dropdown must sit above Leaflet map layers.")
check("notification-item-top" in site_styles, "Notification dropdown must have clear card-style text layout.")
check("renderNotificationList" in site_script, "Shared site script must render detailed notification items.")
check('document.getElementById("top-notification-bell")?.addEventListener("click"' not in dashboard_script, "Dashboard script must not duplicate the shared notification-bell click handler.")
check('"Voice"' not in dashboard_script and '"Voice"' not in main_script, "Alert UI/API must not expose unsupported voice delivery.")
check("Emergency bulletin dispatched" not in main_script, "Backend alert logs must not claim emergency dispatch authority.")
check("Dispatching emergency broadcast" not in dashboard_script, "Dashboard must not claim autonomous emergency broadcasting.")
check("Log alert simulation" in signed_in_dashboard.text, "Dashboard action must be labelled as a simulation log.")
for fake_text in ["Solomon", "S. Ejeh", "823k", "90.4%", "10 / 20", "Move to higher ground", "HYDRA"]:
    check(fake_text not in signed_in_dashboard.text, f"Dashboard must not render hardcoded demo value: {fake_text}")
check("Stations needing review" in signed_in_dashboard.text, "Dashboard must describe elevated stations instead of claiming a population-at-risk estimate.")
check("FloodWatch ML" in signed_in_dashboard.text, "Dashboard model card must use the implemented model identity, not screenshot placeholder branding.")
check('data-contact-email=""' in home_page.text, "Rendered pages must expose empty contact email state when FLOODWATCH_CONTACT_EMAIL is not configured.")
check("your-email@example.com" not in base_template and "your-email@example.com" not in contact_page.text and "your-email@example.com" not in contact_script, "Contact actions must not point to placeholder email addresses.")
check("data-google-placeholder" not in login_page.text and "data-google-placeholder" not in register_page.text and "data-google-placeholder" not in site_script, "Google sign-in must not look actionable until OAuth credentials are configured.")
check("function escapeHtml" in data_script, "Flood-data table rendering must escape user/sensor text.")
check("setInterval(loadTelemetry, 15000)" in data_script, "Flood-data telemetry evidence must auto-refresh during live simulation/hardware demos.")
check("telemetry-source-filter" in public_data_page.text, "Flood-data page must expose a source filter for simulated versus hardware evidence.")
check('TemplateResponse("' not in main_script, "Jinja2 rendering must use Starlette's request-first TemplateResponse signature.")
check("/api/auth" not in query_api_script, "Read-only query helper must not create or log into demo accounts.")
check('if __name__ == "__main__"' in query_api_script, "Query helper must not run network requests merely because it was imported.")
check(DEFAULT_DATABASE_URL == "sqlite:///flood_data.db", "Production database must be file-based SQLite.")

with TestingSessionLocal() as db:
    saved_reports = db.query(models.CommunityReport).all()
check(len(saved_reports) == 0, "Parked community reporting must not create reports by default.")

print("-" * 68)
print("[PASS] Core dashboard/data access, break tests, optional auth shell, parked extras, source switching, XSS guards, and SQLite configuration verified.")

engine.dispose()
if TEST_DATABASE_PATH.exists():
    TEST_DATABASE_PATH.unlink()
TEST_RUNTIME.cleanup()
