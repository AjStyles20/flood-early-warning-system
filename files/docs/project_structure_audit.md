# FloodWatch Project Structure Audit

Date: 2026-08-31
Last updated: 2026-09-08

Operational extension additions: `api/news_feeds.py`, `api/manage_operator.py`, `api/requirements-dev.txt`, `api/test_operational.py`, `api/test_frontend.cjs`, `api/test_http_smoke.py`, `api/templates/pages/evaluation.html`, and `api/static/js/news.js`/`evaluation.js`. Root deployment files are `Dockerfile`, `docker-compose.yml`, `.dockerignore`, and `.github/workflows/ci.yml`. New guides are `docs/operational_platform_guide.md` and `docs/provider_setup.md`. Existing active paths have been preserved; no folders or user evidence were deleted in this pass. Docker runtime files use a persistent `/app/runtime` volume. Tests use their own temporary databases/logs.

This audit records the current project layout, active folders, archived legacy items, generated files, and final-submission recommendations. It exists so the project can be explained as a clean engineering system rather than a scattered prototype workspace.

## Active implementation root

The active application lives in:

```text
files/api/
```

This is the folder used by FastAPI, Jinja2, SQLAlchemy, Pydantic, scikit-learn, tests, the current dashboard, the SQLite database, the trained model artifact, and simulated alert logs.

## Current professional structure

Current structure after the cleanup pass:

```text
Project/
|-- files/
|   |-- api/
|   |   |-- main.py
|   |   |-- database.py
|   |   |-- models.py
|   |   |-- risk_engine.py
|   |   |-- train_model.py
|   |   |-- ml_model.py
|   |   |-- notifications.py
|   |   |-- query_api.py
|   |   |-- weather_forecast.py
|   |   |-- test_api.py
|   |   |-- test_model_training.py
|   |   |-- requirements.txt
|   |   |-- model.pkl
|   |   |-- model_metrics.json
|   |   |-- flood_data.db
|   |   |-- simulated_notifications.jsonl
|   |   |-- simulated_account_notifications.jsonl
|   |   |-- static/
|   |   |   |-- favicon.svg
|   |   |   |-- css/
|   |   |   |   `-- site.css
|   |   |   `-- js/
|   |   |       |-- site.js
|   |   |       |-- dashboard.js
|   |   |       |-- data.js
|   |   |       `-- contact.js
|   |   `-- templates/
|   |       |-- base.html
|   |       `-- pages/
|   |           |-- home.html
|   |           |-- about.html
|   |           |-- projects.html
|   |           |-- news.html
|   |           |-- contact.html
|   |           |-- dashboard.html
|   |           |-- data.html
|   |           |-- settings.html
|   |           `-- auth/
|   |               |-- login.html
|   |               |-- register.html
|   |               `-- confirm_register.html
|   |-- archive/
|   |   |-- README.md
|   |   |-- legacy_scripts/
|   |   |   `-- update_dashboard.py
|   |   `-- old_new_folder_code/
|   |       |-- database.py
|   |       |-- database (1).py
|   |       |-- risk_engine.py
|   |       `-- train_model.py
|   |-- data/
|   |   `-- simulated_telemetry.jsonl
|   |-- docs/
|   |   |-- project_work_log.md
|   |   |-- project_structure_audit.md
|   |   |-- chapter_three_implementation_draft.md
|   |   |-- defense_demo_script.md
|   |   |-- hardware_integration_guide.md
|   |   |-- api_reference.md
|   |   `-- docx_backups/
|   |-- flood_sensor_simulator.py
|   `-- README.md
|-- walkthrough.md
|-- task.md
|-- implementation_plan.md
|-- README.md
|-- 7_Chapters_1_and_2_Draft.docx
`-- 8_Chapters_1_and_2_Draft.docx
```

## Active folders

### `files/api`

Purpose: active backend, Jinja2 templates, static assets, model artifacts, database, and tests.

Status: keep.

### `files/api/templates`

Purpose: active server-rendered frontend pages.

Status: keep.

### `files/api/static`

Purpose: active CSS and JavaScript for the Jinja2 pages.

Status: keep.

### `files/data`

Purpose: simulator fallback telemetry log.

Status: keep for demonstration evidence.

### `files/docs`

Purpose: engineering log, structure audit, and Word-document backups.

Status: keep.

Current defense-support documents:

- `project_work_log.md`
- `project_structure_audit.md`
- `chapter_three_implementation_draft.md`
- `defense_demo_script.md`
- `hardware_integration_guide.md`
- `api_reference.md`

### `files/archive`

Purpose: recoverable holding area for old prototype files that are no longer part of the active system.

Status: keep during development; exclude from final submission if the supervisor only wants the clean core implementation.

### Root `README.md`

Purpose: front-door document explaining project scope, quick-start commands, folder layout, corrected ML evidence, and safety/accessibility guardrails.

Status: keep.

## Archived legacy items

### `files/archive/old_new_folder_code`

Original path:

```text
New folder/
```

Observed contents:

```text
database.py
database (1).py
risk_engine.py
train_model.py
```

Assessment: duplicate/older code copies. The old folder name was not professional, so it was archived under a clear name instead of being deleted.

### `files/archive/legacy_scripts/update_dashboard.py`

Original path:

```text
update_dashboard.py
```

Assessment: old one-off script that targeted legacy static dashboard assumptions. It is no longer part of the active Jinja2/FastAPI application.

## Removed generated items

The following generated Python cache folders were removed:

```text
files/__pycache__/
files/api/__pycache__/
```

These folders contain Python bytecode cache files. Python may recreate them during test runs or normal execution, and they should not be treated as source code.

## Items intentionally left untouched

### `~$Chapters_1_and_2_Draft.docx`

Assessment: Microsoft Word temporary lock file.

Decision: left untouched. It should only be removed after Word is closed, because deleting it while the document is open can interfere with Word's document-locking behavior.

### Word chapter drafts

The Word documents remain at the project root:

```text
7_Chapters_1_and_2_Draft.docx
8_Chapters_1_and_2_Draft.docx
```

Backups from the documentation update pass remain under:

```text
files/docs/docx_backups/
```

## Naming recommendations

Recommended conventions:

- Use lowercase snake_case for Python files.
- Use descriptive page names for Jinja2 templates.
- Keep generated artifacts clearly named:
  - `model.pkl`
  - `model_metrics.json`
  - `flood_data.db`
  - `simulated_notifications.jsonl`
  - `simulated_account_notifications.jsonl`
- Avoid final-submission names like:
  - `New folder`
  - `database (1).py`
  - one-off scripts that overwrite active pages

## Do not rename active source files without checking imports

These files are currently imported directly and should not be renamed casually:

- `main.py`
- `database.py`
- `models.py`
- `risk_engine.py`
- `train_model.py`
- `ml_model.py`
- `notifications.py`
- `weather_forecast.py`
- `flood_sensor_simulator.py`

Renaming them requires updating imports, tests, run commands, and documentation together.

## Final packaging recommendation

For the supervisor/demo copy, keep:

- `files/api/`
- `files/data/`
- `files/docs/`
- `files/flood_sensor_simulator.py`
- `files/README.md`
- `README.md`
- root documentation files

Exclude if not needed:

- `files/archive/`
- regenerated `__pycache__/` folders
- `~$*.docx` Word temporary lock files

This keeps the submitted project focused on sensor/simulator input, database storage, separate experimental ML evidence, current-state risk analysis, an accessible GIS dashboard, and an auditable alert workflow. EmailJS/Twilio provider adapters exist, but their live recipient delivery has not been verified.
