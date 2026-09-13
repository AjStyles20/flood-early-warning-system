# FloodWatch Nigeria

Intelligent Flood Early Warning and Decision Support System.

This project is a portable flood-monitoring prototype using Nigeria as the case-study deployment. It combines simulated or hardware-ready sensor telemetry, persistent database storage, a corrected future-horizon ML model, four-tier flood-risk decision support, an accessible GIS dashboard, and simulated multi-channel alert logging.

The system is decision support only. It does not replace official emergency agencies and must not issue autonomous commands. Risk messages are written to help users and responders interpret conditions and follow official guidance.

## Active project scope

The user has authorized an operational-platform extension: operator/admin roles, CSV input, persistent alert review, model charts/PDF reports, configurable external news, and deployment/CI configuration. See the [operational guide](files/docs/operational_platform_guide.md) for current behavior and test commands, and [provider setup](files/docs/provider_setup.md) for the required keys and limitations. This product authorization is separate from supervisor approval of revised academic objectives.

Core approved pipeline:

1. Sensor or simulator sends telemetry.
2. FastAPI validates the reading.
3. SQLAlchemy stores it in file-based SQLite.
4. The risk engine assigns Low, Moderate, High, or Severe status.
5. The ML wrapper adds future-risk probability from the trained model.
6. The Leaflet/OpenStreetMap dashboard displays map markers and an accessible text station list.
7. Simulated web, email, and SMS alerts are logged for alert-worthy conditions.

Parked until supervisor approval:

- community reporting / resident corroboration
- WhatsApp alerting
- localization UI
- live messaging activation (provider setup and a separately authorized delivery test are still needed)

## Project layout

```text
Project/
|-- files/
|   |-- api/        active FastAPI backend, Jinja2 pages, static assets, tests, model, and database
|   |-- data/       simulator fallback telemetry log
|   |-- docs/       engineering log and structure audit
|   |-- archive/    recoverable legacy prototype files
|   `-- flood_sensor_simulator.py
|-- implementation_plan.md
|-- task.md
|-- walkthrough.md
`-- README.md
```

More detail is recorded in [files/docs/project_structure_audit.md](files/docs/project_structure_audit.md).

## Defense documents

- [files/docs/chapter_three_implementation_draft.md](files/docs/chapter_three_implementation_draft.md) gives a Chapter Three methodology and implementation draft based on the current verified code.
- [files/docs/defense_demo_script.md](files/docs/defense_demo_script.md) gives a step-by-step viva/demo script with commands, talking points, expected outputs, and troubleshooting notes.
- [files/docs/hardware_integration_guide.md](files/docs/hardware_integration_guide.md) explains how a physical sensor node can send the same tested JSON shape as the simulator.
- [files/docs/api_reference.md](files/docs/api_reference.md) summarizes the active API endpoints for telemetry, risk status, dashboard/data pages, and validation behavior.
- [walkthrough.md](walkthrough.md) gives a shorter system walkthrough for quick revision.

## Quick start

From PowerShell:

```powershell
cd C:\Users\User\Documents\Word_Document\Project\files\api
py -m pip install -r .\requirements.txt
py -u .\train_model.py
py -u .\test_model_training.py
py -u .\test_api.py
py -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Then open:

```text
http://127.0.0.1:8000/dashboard
```

If port `8000` is blocked on Windows, start on a higher local port:

```powershell
py -m uvicorn main:app --reload --host 127.0.0.1 --port 8030
```

Then open `http://127.0.0.1:8030/dashboard`.

In a second PowerShell terminal, populate the dashboard:

```powershell
cd C:\Users\User\Documents\Word_Document\Project
py .\files\flood_sensor_simulator.py --mode flood --ticks 30
```

Optional read-only API check while the server is running:

```powershell
py .\files\api\query_api.py --view risk --source hybrid
```

Important PowerShell note: paste only the command text, not the `PS C:\...>` prompt or quote marks from chat formatting.

## Correct ML evidence

The saved model uses simulator-generated telemetry only. It predicts whether a below-danger reading will cross the danger level within the next 6 simulator ticks.

The earlier perfect threshold-baseline result is superseded and must not be used as predictive evidence because it came from a circular current-threshold label.

Current corrected evidence is stored in [files/api/model_metrics.json](files/api/model_metrics.json) and verified by [files/api/test_model_training.py](files/api/test_model_training.py).

Latest verified F1 scores from simulator-generated telemetry:

- threshold baseline: `0.6666666666666666`
- Logistic Regression: `0.7085714285714285`
- Random Forest: `0.975609756097561`

## Accessibility and safety guardrails

- The dashboard provides both a visual map and a text station list.
- Risk is communicated by text plus colour, never colour alone.
- Alert messages are simulated/logged unless real providers are configured and tested.
- The river-context layer is schematic only, not an official flood-boundary dataset.
- SQLite defaults to `sqlite:///flood_data.db`; do not replace it with in-memory `sqlite://` for normal use.
- Dashboard and Flood Data source modes are explicit: `simulated`, `hardware`, and `hybrid`.
