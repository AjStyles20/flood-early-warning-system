# Project Task Tracker

## Operational extension status — 2026-09-08

- [x] Add and locally test operator/admin authorization and server-side role provisioning.
- [x] Add and locally test CSV validation, persistent alert workflow and audit history.
- [x] Add synthetic evaluation charts, confusion counts, and complete downloadable scenario/model PDFs.
- [x] Add and test configurable news adapters with isolated provider fixtures/failures.
- [x] Verify key pages and API responses through an isolated HTTP service.
- [x] Add Docker/Compose and CI definitions; parse deployment YAML locally.
- [ ] Run container build/health with Docker installed and execute hosted GitHub Actions.
- [ ] Configure a real news-provider key/feed and verify that subscription/network.
- [x] Obtain specific approval for EmailJS contact-data transfer (user approved names, email addresses, subjects and messages on form submission; 2026-09-09).
- [x] Complete and locally verify the environment-configured EmailJS contact sender, including draft preservation, timeout/error handling and duplicate-click protection (2026-09-10; mocked provider responses, not live delivery).
- [ ] Configure the EmailJS service/template/public key locally and record a deliberate live contact-message delivery check; mocked tests do not prove delivery.
- [ ] Configure and verify real alert/OTP messaging separately; it remains simulated.

Current setup: [operational guide](files/docs/operational_platform_guide.md), [provider setup](files/docs/provider_setup.md). Operator work is user-authorized; academic scope changes remain subject to supervisor agreement.

## Completed core work

- [x] Implemented the FastAPI service in [files/api/main.py](files/api/main.py)
- [x] Added persistent SQLite configuration in [files/api/database.py](files/api/database.py)
- [x] Built SQLAlchemy/Pydantic data models in [files/api/models.py](files/api/models.py)
- [x] Implemented the four-tier safety-first risk engine in [files/api/risk_engine.py](files/api/risk_engine.py)
- [x] Created the model-serving wrapper in [files/api/ml_model.py](files/api/ml_model.py)
- [x] Corrected the ML training target in [files/api/train_model.py](files/api/train_model.py)
- [x] Added leakage-guard testing in [files/api/test_model_training.py](files/api/test_model_training.py)
- [x] Added simulated web/email/SMS alert logging in [files/api/notifications.py](files/api/notifications.py)
- [x] Built the active accessible dashboard with Jinja2 in [files/api/templates/pages/dashboard.html](files/api/templates/pages/dashboard.html)
- [x] Upgraded the dashboard map with risk rings, station labels, keyboard-friendly station focus, richer popups, and map accessibility text
- [x] Added map search, risk filtering, clear-filter handling, and map tile-health feedback
- [x] Added selected-station details and freshness/staleness indicators for telemetry readings
- [x] Added a clearly labelled schematic river-context overlay for Nigeria case-study interpretation
- [x] Added a project favicon and updated Jinja2 rendering to remove Starlette `TemplateResponse` deprecation noise during demos
- [x] Added a root [README.md](README.md) as the project front-door with quick start, scope, layout, and safety notes
- [x] Added [chapter_three_implementation_draft.md](files/docs/chapter_three_implementation_draft.md) and [defense_demo_script.md](files/docs/defense_demo_script.md)
- [x] Added [hardware_integration_guide.md](files/docs/hardware_integration_guide.md) and [api_reference.md](files/docs/api_reference.md)
- [x] Simplified [query_api.py](files/api/query_api.py) into a read-only public endpoint helper instead of an auth/account demo helper
- [x] Clarified dashboard telemetry source modes so Simulated, Hardware, and Hybrid have visible explanations
- [x] Made the Flood Data telemetry table refresh automatically and support source filtering
- [x] Updated the optional account shell so registration captures phone contact details, confirms details before account creation, and returns users to Home by default
- [x] Added guarded optional account deletion with feedback reason, simulated verification code, and simulated deletion notice
- [x] Verified the API, dashboard access, break tests, source switching, parked extras, and SQLite configuration through [files/api/test_api.py](files/api/test_api.py)
- [x] Cleaned the top-level structure by archiving old prototype files under `files/archive/`
- [x] Added `.gitignore` rules for caches, local environment files, database/log artifacts, and Word lock files

## Verified current state

- Telemetry is stored in persistent SQLite, not in-memory SQLite.
- The core dashboard and flood data page can be viewed without account login.
- Simulated, hardware, and hybrid source modes are supported.
- Source modes are explained in the dashboard so users can understand the difference between simulator-only, hardware-only, and hybrid comparison views.
- The dashboard includes a map plus a text station list for accessibility.
- The map includes risk-ring planning overlays, station labels, source/layer controls, and station-list buttons that focus markers.
- Users can search/filter map stations without losing the screen-reader text alternative.
- The dashboard warns users if the base map tiles are slow or unavailable while keeping station data visible.
- The dashboard identifies fresh, watch-aged, stale, and signal-check readings so old telemetry is not mistaken for live sensor truth.
- The river-context layer is labelled as schematic support only, not an official flood-boundary dataset.
- Browser requests for `/favicon.ico` return the FloodWatch SVG icon instead of a distracting 404.
- Risk messages remain safe and end with "follow official guidance."
- Active alert simulation covers web, email, and SMS.
- The Flood Data page loads newest telemetry first and refreshes every 15 seconds.
- Optional account deletion is protected by a simulated verification code and explicit `DELETE` confirmation.
- ML training now predicts future danger-level crossing within a 6-tick horizon, instead of repeating the current threshold label.
- The old perfect baseline result is superseded and must not be cited as predictive evidence.
- Legacy prototype files are recoverable in `files/archive/`, not mixed with the active code.
- Generated Python cache folders were removed from the visible project tree; `.gitignore` keeps them out of future submissions.

## Current focus before defense

- [ ] Keep the core pipeline stable: simulator/hardware input -> database -> ML/risk assessment -> dashboard -> alert log.
- [ ] Use the corrected `model_metrics.json` in documentation and presentation materials.
- [ ] Prepare Chapter Three around the actual stack: FastAPI, SQLAlchemy, Pydantic, SQLite, scikit-learn, Leaflet/OpenStreetMap.
- [ ] Add screenshots of the running dashboard and API test output.
- [ ] If hardware is available, connect it using the existing `POST /api/telemetry` JSON shape with `data_source: "hardware"`.
- [ ] Keep every performance claim tied to visible test output.
- [x] Review and apply the safe structure cleanup recorded in [files/docs/project_structure_audit.md](files/docs/project_structure_audit.md).

## Parked unless supervisor approves

- [ ] Community reporting / resident corroboration
- [ ] WhatsApp alert channel
- [ ] Localization UI
- [ ] Advanced account-dependent product flows
- [ ] Production account management

## Notes

The project should now be presented as a core intelligent flood early-warning and decision-support system, with optional product ideas clearly separated from approved objectives. That separation protects the project from scope creep while preserving useful future-work paths.
