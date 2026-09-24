# FloodWatch Sensor and Backend Workspace

This folder contains the working implementation for the Intelligent Flood Early Warning and Decision Support System.

Current operational extension (2026-09-08): operator/admin permissions, CSV uploads, alert acknowledgement/escalation/audit, saved evaluation charts and PDFs, external news adapters, and deployment configuration. The [operational guide](docs/operational_platform_guide.md) supersedes earlier scope notes about parking operator accounts. [Provider setup](docs/provider_setup.md) explains keys and what remains simulated. Academic objective changes still need supervisor agreement.

## Active implementation

- `api/` contains the FastAPI backend, database models, ML training code, risk engine, notification logging, tests, Jinja2 templates, CSS, and JavaScript.
- `flood_sensor_simulator.py` simulates multi-station IoT telemetry and can post readings directly to the FastAPI API.
- `data/simulated_telemetry.jsonl` stores simulator fallback logs.
- `archive/` stores recoverable legacy prototype files that are no longer part of the active application.
- `docs/project_structure_audit.md` records active folders, archived legacy files, generated files, and final packaging advice.
- `docs/chapter_three_implementation_draft.md` provides a Chapter Three implementation draft based on the current verified system.
- `docs/defense_demo_script.md` provides a demo-day script, talking points, expected outputs, and troubleshooting notes.
- `docs/hardware_integration_guide.md` explains the tested JSON contract for plugging in a physical sensor node later.
- `docs/api_reference.md` summarizes the active API endpoints and validation behavior.

The active dashboard is served from `api/templates/pages/dashboard.html`.
The shared Jinja2 base template also advertises `api/static/favicon.svg`, and `/favicon.ico` is served by FastAPI so the browser does not create unnecessary 404 noise during demonstrations.

## Core run commands

From the repository root:

```powershell
cd C:\Users\User\Documents\Word_Document\Project\files\api
py -u .\train_model.py
py -u .\test_model_training.py
py -u .\test_api.py
py -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Open the dashboard:

```text
http://127.0.0.1:8000/dashboard
```

If Windows blocks port `8000`, run on a higher local port:

```powershell
py -m uvicorn main:app --reload --host 127.0.0.1 --port 8030
```

Then open `http://127.0.0.1:8030/dashboard`.

The dashboard map includes:

- OpenStreetMap and satellite layer switching
- simulated/hardware/hybrid source switching
- station search by name, ID, risk, source, or signal
- risk-level filtering
- risk-ring planning overlays
- a schematic river-context overlay for Niger-Benue, Lake Chad, and coastal/drainage interpretation
- station labels
- map tile-health feedback
- selected-station details
- freshness/staleness labels based on telemetry timestamp and signal state
- popups with water level, rainfall, flow, battery, signal, ML probability, and safe guidance
- a text station list with buttons that focus the matching marker for keyboard users
- a project favicon so the browser tab has a clear FloodWatch identity and the server log stays clean

The river-context overlay is schematic and used for dashboard interpretation only. It is not presented as an official flood-boundary dataset.

Run the simulator from a second terminal:

```powershell
cd C:\Users\User\Documents\Word_Document\Project
py .\files\flood_sensor_simulator.py --mode flood --ticks 30
```

Optional read-only API check while the server is running:

```powershell
cd C:\Users\User\Documents\Word_Document\Project
py .\files\api\query_api.py --view risk --source hybrid
```

## Telemetry schema

Each simulator or hardware reading uses this JSON shape:

```json
{
  "station_id": "STN-01",
  "station_name": "Lokoja (Niger-Benue confluence)",
  "data_source": "simulated",
  "lat": 7.7999,
  "lon": 6.7333,
  "timestamp": "2026-08-31T12:00:00+00:00",
  "water_level_m": 2.174,
  "danger_level_m": 5.5,
  "rainfall_mm_hr": 5.03,
  "flow_rate_m3s": 25.07,
  "battery_pct": 100.0,
  "signal": "online"
}
```

For physical hardware, send:

```json
"data_source": "hardware"
```

The `GET /api/risk-status` endpoint returns the latest station status plus calculated risk fields for the map. It includes telemetry context such as rainfall, flow rate, battery percentage, and signal state so the dashboard does not need a second request for each popup.

## Database

The default database is file-based SQLite:

```text
sqlite:///flood_data.db
```

Do not replace this with `sqlite://` for normal application use. The current regression tests also use a temporary file-based SQLite database so the persistence rule is exercised during testing.

## Corrected ML target

The model is trained to predict future threshold crossing, not current threshold state.

Current features:

- water-level ratio
- rainfall intensity
- flow rate
- rate of rise

Prediction label:

- whether a station that is below danger level now reaches danger level within the next 6 simulator ticks

This avoids the earlier circularity bug where the baseline and label used the same current threshold condition.

## Active alert channels

The flood alert workflow records these channels:

- web
- email
- SMS

For alert-worthy hardware telemetry, the application attempts email and SMS through EmailJS and Twilio when their environment variables are configured. Simulator readings do not contact providers by default; to deliberately test delivery from a simulator, set `FLOOD_EWS_ALLOW_SIMULATED_PROVIDER_DELIVERY=true` with controlled recipients. Without provider configuration, the channel outcome is `not_configured`. An accepted provider request is recorded as `sent`; this records provider acceptance, not confirmed recipient delivery. The operator's **Log alert simulation** action records a test bulletin and does not send messages. Account verification and account deletion notices remain local simulations. Subsequent readings at the same or lower risk level reuse the active alert's dispatch result; a risk escalation makes a new provider attempt. Concurrent ingest workers can still race, so production dispatch needs an atomic claim or queue before unrestricted live use.

## Optional account-shell notes

The optional account pages are not required for the approved core demo. They currently demonstrate:

- confirm-before-create registration;
- email plus phone-number capture for simulated contact preferences;
- logged-in homepage behavior without a redundant guest call-to-action;
- settings/profile updates;
- two-step account deletion with a simulated verification code and feedback reason.

These account notices are logged locally in `api/simulated_account_notifications.jsonl`; they are not real provider messages.

## Scope control

Parked until supervisor approval:

- community reporting / resident corroboration
- WhatsApp alerting
- localization UI
- advanced account-dependent product flows

These ideas may be useful future work, but they should not be presented as approved core features.
