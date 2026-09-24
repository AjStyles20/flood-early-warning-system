# FloodWatch Nigeria

Intelligent Flood Early Warning and Decision Support System.

FloodWatch is an engineering prototype and research testbed for flood early-warning decision support, with Lokoja on the River Niger as the current scientific case study. The working platform combines controlled simulation, a physical Pico-to-API integration path, normalized MySQL-capable persistent storage, threshold-state decision support, an accessible GIS dashboard, and alert workflow infrastructure. Historical observational research is deliberately separated from the live application.

The system is decision support only. It does not replace official emergency agencies and must not issue autonomous commands. Risk messages are written to help users and responders interpret conditions and follow official guidance.

## Active project scope

The user has authorized an operational-platform extension: operator/admin roles, CSV input, persistent alert review, model charts/PDF reports, configurable external news, and deployment/CI configuration. See the [operational guide](files/docs/operational_platform_guide.md) for current behavior and test commands, and [provider setup](files/docs/provider_setup.md) for the required keys and limitations. This product authorization is separate from supervisor approval of revised academic objectives.

Current engineering pipeline:

1. A local prototype node or controlled simulator sends telemetry.
2. FastAPI validates and stores the reading.
3. The current-state engine evaluates configured threshold bands.
4. The dashboard displays source-aware status and the alert workflow.
5. The saved synthetic ML model may be displayed only for simulated development records; it does not determine the current threshold state and is not applied to physical observations.

Scientific research follows a separate path: source provenance -> raw-data audit -> accepted observations -> preprocessing -> target/split definition -> experiment -> evaluation. Experiment 001 remains blocked until its protocol is frozen and explicitly released for execution.

Parked until supervisor approval:

- community reporting / resident corroboration
- WhatsApp alerting
- localization UI
- live messaging activation (provider setup and a separately authorized delivery test are still needed)

## 72-hour defense closure

The project is now in closure rather than feature-expansion mode. The frozen minimum defense boundary, P0/P1 priorities, three-day execution order and stop rule are recorded in [files/docs/defense_closure_baseline.md](files/docs/defense_closure_baseline.md).

![Defense-ready core architecture](files/docs/diagrams/floodwatch_defense_ready_core_architecture.svg)

## Project layout

```text
Project/
|-- files/
|   |-- api/        active FastAPI backend, Jinja2 pages, static assets, tests, model, and database
|   |-- data/       simulator fallback telemetry log
|   |-- docs/       engineering log, structure audit, and alignment specification\n|   |-- research/   historical research boundary and provenance manifests
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
py -u .\test_observation_contract.py
py -u .\test_telemetry_adapter.py
py -u .\test_risk_separation.py
py -u .\test_api.py
py -u .\test_operational.py
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

## Synthetic development ML evidence

The saved model is retained as development evidence from simulator-generated telemetry only. It predicts whether a below-danger simulated reading will cross the simulator danger level within the next 6 simulator ticks. It is frozen: it is not the thesis model, is not applied to physical observations, and must not be presented as real Lokoja predictive performance.

The earlier perfect threshold-baseline result is superseded and must not be used as predictive evidence because it came from a circular current-threshold label.

Current corrected evidence is stored in [files/api/model_metrics.json](files/api/model_metrics.json) and verified by [files/api/test_model_training.py](files/api/test_model_training.py).

Latest verified F1 scores from simulator-generated telemetry:

- threshold baseline: `0.6666666666666666`
- Logistic Regression: `0.7085714285714285`
- Random Forest: `0.975609756097561`

## Scientific implementation alignment

The current refactor is governed by [files/docs/implementation_alignment_spec_v1.md](files/docs/implementation_alignment_spec_v1.md). Key rules include:

- unavailable is not zero;
- prototype/demo thresholds are not official Lokoja thresholds;
- simulated, observed, gridded, reanalysis, modelled, and derived evidence remain distinguishable;
- current threshold state and forecast probability are separate concepts;
- the Pico potentiometer is a controlled analogue input, not a Lokoja field water-level measurement;
- no B3/B4 experiment or new model training is authorized by the engineering refactor.

## Accessibility and safety guardrails

- The dashboard provides both a visual map and a text station list.
- Risk is communicated by text plus colour, never colour alone.
- Alert messages are simulated/logged unless real providers are configured and tested.
- The river-context layer is schematic only, not an official flood-boundary dataset.
- MySQL is the target development/operational DBMS. SQLite remains the default compatibility/test fallback when `FLOOD_EWS_DATABASE_URL` is not set; do not confuse SQLite-only execution with the MySQL deployment gate.
- Dashboard and Flood Data source modes are explicit: `simulated`, `hardware`, and `hybrid`.
