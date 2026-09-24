# Operational platform guide

Updated: 2026-09-08. This records the product expansion authorized in the chat. It does not assert that Dr. Julius Makinde has approved revised academic objectives. The earlier core pipeline remains intact; community reporting and live WhatsApp delivery remain parked.

## Start and test

Copy commands only, without `PS ...>`, `>>`, Markdown quote marks, or literal `\n`. Use one terminal for the service and another for the simulator.

From the project root, install development dependencies and run checks:

```powershell
py -m pip install -r .\files\api\requirements-dev.txt
py -m compileall -q .\files\api .\files\flood_sensor_simulator.py
node .\files\api\test_frontend.cjs
cd .\files\api
py -u .\test_model_training.py
py -u .\test_api.py
py -u .\test_operational.py
py -u .\test_http_smoke.py
```

The test databases and notification logs are created in temporary directories. The HTTP smoke test starts and stops its own service. Tests do not register accounts in, delete, or overwrite `flood_data.db`.

Start the application from `files/api`:

```powershell
py -m uvicorn main:app --reload --host 127.0.0.1 --port 8030
```

Open `http://127.0.0.1:8030/`. The dashboard is `/dashboard`, telemetry evidence is `/data`, model evidence is `/evaluation`, and external articles are `/news`. If a port is unavailable, select another free local port and use it in both the browser and simulator API URL.

In a second terminal, from the project root:

```powershell
py .\files\flood_sensor_simulator.py --mode flood --ticks 30 --api-url http://127.0.0.1:8030/api/telemetry
```

## Roles and sessions

Public users can read the dashboard, telemetry, risk, news, and aggregate synthetic model evidence. Personal Settings requires an account. CSV ingestion, scenario runs, alert workflow changes and detailed audit history require an operator or admin session. Admins can list accounts and change roles through the API.

Register and confirm the intended account first. Then, from the trusted server terminal in `files/api`, use the same database configuration as the running service:

```powershell
$FloodAccount = Read-Host 'Email of the existing account to authorize'
py .\manage_operator.py $FloodAccount --role admin
```

Use `--role operator` to grant operational access without account-management privileges. Refresh the page after the change. The command refuses nonexistent accounts; no default password or automatic promotion by an unverified email address is configured. Do not give users server-terminal access merely to let them register.

Session tokens are random; the database stores their hashes, expiry and revocation state. Browser cookies are HTTP-only and SameSite=Lax. Logout uses POST and revokes the current session. Cross-site browser writes are rejected. Set `FLOOD_EWS_SECURE_COOKIES=1` when serving over HTTPS; keep `0` for a local HTTP demo. This is a prototype and does not claim a complete production authentication audit, email ownership verification, MFA, or distributed pending-registration storage.

## CSV and sensor provenance

The Flood Data page shows CSV upload controls to operators. Upload a UTF-8 `.csv` up to 2,000,000 bytes with these headers:

```csv
station_id,station_name,data_source,lat,lon,timestamp,water_level_m,danger_level_m,rainfall_mm_hr,flow_rate_m3s,battery_pct,signal
CSV-01,Example household gauge,hardware,7.8,6.7,2026-09-08T10:00:00Z,2.4,5.0,10,30,95,online
```

The example is test input, not evidence of a physical sensor. `data_source` may be omitted (defaults to simulated); all other listed fields are required. Upload at most 2,000 rows per request. Each valid row is saved; invalid rows are counted and up to 25 error descriptions returned. Imports are partial, not all-or-nothing. Structural CSV parse failures are rejected before saving. Duplicate headers, malformed row widths, invalid coordinates, non-finite numeric values and non-positive danger levels are rejected. Normalized observation identity is now protected by the shared replay/conflict policy and a database UNIQUE constraint over station + variable + source + observed timestamp. CSV behavior must therefore be interpreted through the current ingestion path rather than the earlier unconditional-duplicate note.

Simulation and hardware are stored separately. Hybrid selects the higher current risk from the available sources for a station. Selecting Hardware does not connect or authenticate a device: it filters readings explicitly tagged `hardware`. The dashboard and evidence table poll every 15 seconds.

`FLOOD_EWS_INGEST_TOKEN` optionally protects `POST /api/telemetry`; sensor requests then need `X-Ingest-Token`. Without the variable, ingestion remains open for the local demo. Configure authentication before exposing ingestion publicly. A source label is provenance supplied by the sender, not proof of a hardware measurement.

## Alert workflow

Moderate/High/Severe readings create persistent alert events. Repeated readings update an active station/source alert. Operators can acknowledge, escalate or resolve it, with a note. The queue's View history button retrieves the audit trail. Private operator notes and audit history require operator access.

Allowed transitions are `new -> acknowledged/escalated/resolved`, `acknowledged -> escalated/resolved`, and `escalated -> resolved`. Resolved events cannot be reopened by those endpoints. A later elevated reading can create a new event. Resolution records an operator's review status; it does not change the sensor evidence or prove the area is safe.

Escalation is an internal workflow status. Web/email/SMS labels continue to describe simulation; they do not claim an authority was contacted or a message delivered. All risk wording defers to official guidance. Legacy JSONL copies are not mixed back into a populated persistent queue, avoiding duplicate alerts.

## Evaluation evidence

The evaluation page compares threshold baseline, Logistic Regression and Random Forest using saved holdout results. Charts include text labels and values, with accuracy, precision, recall, F1 and false-positive/false-negative counts. Missing metrics are labelled unavailable instead of displayed as zero.

The prediction target remains a future danger-threshold crossing within six simulator ticks, using current features. Training and testing split by episode. All results are simulator-generated; there is no field-validated performance claim.

Each dashboard scenario stores before/after risk, water level, operator and a snapshot of the saved evaluation. Its PDF is a scenario record plus that snapshot. A single injected reading does not supply enough ground truth to calculate a new scenario-specific accuracy score. PDFs wrap and paginate text so trailing FP/FN values and guidance are retained. They use a basic Latin-1 font; the HTML page provides the accessible text alternative.

## Deployment

MySQL is the target development/operational DBMS. Docker Compose provisions MySQL 8.4 and supplies the API with a `mysql+pymysql` connection through `FLOOD_EWS_DATABASE_URL`. SQLite remains a compatibility/test fallback when that variable is absent. The saved simulator model is development evidence and should not be retrained merely to start or demonstrate the operational application.

From the project root with Docker installed:

```powershell
docker compose up --build -d
docker compose ps
docker compose logs --tail 40
```

`GET /health` returns 200 when the database is reachable and 503 when it is unavailable; model availability is a separate field. Missing news credentials do not make core monitoring unhealthy. The GitHub Actions workflow runs Python/API/model tests, JavaScript checks, HTTP health checks, container build and container health verification. A workflow file is not evidence of a successful hosted CI run.

Hosted GitHub Actions is now verified and includes the MySQL 8.4 integration gate. Local Docker/MySQL Workbench execution on the user's defense laptop remains a separate environment check and must not be inferred from CI. Pending account confirmation/deletion state is process-local; use a single service worker for the current prototype.

See [provider_setup.md](provider_setup.md) for external feeds and messaging preparation, and [project_work_log.md](project_work_log.md) for exact observed test evidence.


## Defense closure status — 2026-09-24

The active closure baseline is [defense_closure_baseline.md](defense_closure_baseline.md). During the three-day window, core vertical functionality, physical regression, evidence packaging and defense documentation take precedence over optional feature expansion.
