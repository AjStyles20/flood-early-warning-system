# FloodWatch Final Academic Closure Record

Status: current defense baseline — 2026-09-28

## 1. Working academic title

**Development and Evaluation of an Intelligent Flood Early Warning and Decision Support System: A Comparative Study of Conventional and Lightweight Machine-Learning Warning Strategies**

The exact title remains subject to supervisor/department approval. This file records the evidence-aligned project position and must not be used to claim approval that has not been received.

## 2. Primary research question

> At equivalent warning horizons, does a lightweight data-driven predictor provide materially better anticipation of hydrological high-flow threshold crossings than a calibrated, interpretable trend-based warning rule using independent Lokoja observations?

A possible RQ2 extension is the incremental value of hydrologically justified external information such as upstream Niger/Benue conditions and basin rainfall. RQ2 is **not** represented as completed evidence in the current defense baseline.

## 3. Engineering state

The verified engineering prototype includes:

- FastAPI telemetry ingestion and validation;
- source/provenance-aware observation handling;
- normalized MySQL-capable persistence with SQLite CI compatibility;
- transparent current-state threshold assessment;
- dashboard and historical/data views;
- authentication/operator workflows;
- persistent advisory alert workflow/audit;
- controlled simulator support; and
- a previously demonstrated Raspberry Pi Pico -> USB serial -> Python bridge -> FastAPI physical path.

The Pico/potentiometer path is a controlled physical integration proof, not a calibrated Lokoja river gauge.

## 4. Experiment 001

Experiment 001 has been completed using GRDC station 1834101 mean daily discharge for the River Niger at Lokoja.

Frozen temporal design:

- training: 2004-2014;
- validation: 2015-2019;
- final holdout: 2020-2025;
- primary training-derived Q95 high-flow boundary: 18,980.0 m3/s;
- horizons: 1, 3, 5 and 7 days;
- B3: calibrated interpretable trend rule;
- B4: lightweight Random Forest using local discharge history only.

The Q95 boundary is an experimental high-flow boundary, **not** an official NIHSA discharge warning threshold.

### Primary Q95 results

| Horizon | B3 CSI | RF CSI | B3 F1 | RF F1 | B3 FAR | RF FAR | B3 event recall | RF event recall | B3 mean lead | RF mean lead |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 day | 0.500 | 0.500 | 0.667 | 0.667 | 0.400 | 0.400 | 0.750 | 0.750 | 1.00 d | 1.00 d |
| 3 days | 0.727 | 0.667 | 0.842 | 0.800 | 0.111 | 0.200 | 1.000 | 1.000 | 2.00 d | 2.00 d |
| 5 days | 0.533 | 0.522 | 0.696 | 0.686 | 0.000 | 0.400 | 1.000 | 1.000 | 3.25 d | 4.25 d |
| 7 days | 0.409 | 0.455 | 0.581 | 0.625 | 0.250 | 0.483 | 0.750 | 1.000 | 5.33 d | 6.00 d |

## 5. Research conclusion

The evidence does **not** establish a stable material Random-Forest advantage over the strong interpretable baseline.

- 1 day: tie on the reported primary metrics.
- 3 days: B3 is stronger with fewer false alarms.
- 5 days: Random Forest gains mean lead time but incurs a much larger false-alarm penalty.
- 7 days: Random Forest improves recall/lead time but again with substantially higher FAR.

This is a valid mixed/negative result. It must not be rewritten as "AI proved better."

## 6. Architecture decision

The operational current-state/threshold engine remains the default. The Random Forest remains in the research plane and is not promoted to override current operational state.

This decision follows the experimental evidence rather than the original assumption that additional predictive complexity must be better.

## 7. Contribution boundary

FloodWatch does **not** claim:

- a new Random Forest algorithm;
- the first AI/IoT flood-warning system;
- that water level/discharge is the sole cause of flooding;
- an official Lokoja discharge warning threshold;
- Lokoja field validation of the physical node;
- nationwide operational predictive validation; or
- proven reductions in mortality, evacuation time or economic loss.

The defensible contribution is:

1. a functioning source-aware flood monitoring and decision-support prototype;
2. a normalized provenance architecture that separates evidence types;
3. an explicit operational/research boundary;
4. a leakage-resistant real-data comparison against a serious interpretable baseline; and
5. an evidence-driven conclusion about when additional predictive complexity is or is not justified.

## 8. Hydrological interpretation

Local Lokoja discharge/stage is treated as a hydrological response/state and warning variable, not the sole cause of flooding. Upstream Niger/Benue conditions, basin rainfall, catchment state, floodplain/channel characteristics and reservoir operations may affect flood generation.

The strongest future research extension is therefore an incremental-value test of hydrologically justified external information rather than arbitrary sensor expansion.

## 9. Remaining physical/local closure

The major evidence that still requires the user's physical environment is the post-migration vertical regression:

```text
Raspberry Pi Pico
-> actual USB/COM port
-> Python serial bridge
-> FastAPI /api/telemetry
-> MySQL normalized persistence
-> current-state/normalized read
-> dashboard
```

Final screenshots and live-demo rehearsal also require the local machine. These must remain marked pending until actually run.

## 10. Canonical academic artifacts

Research:

- `files/research/experiment_001.py`
- `files/research/experiment_001_results.csv`
- `files/research/experiment_001_results.md`

Thesis/result drafts:

- `files/docs/chapter_three_implementation_draft.md`
- `files/docs/chapter_four_results_draft.md`
- `files/docs/chapter_five_conclusion_draft.md`

Design figures:

- `files/docs/diagrams/floodwatch_evidence_to_decision_support.svg`
- `files/docs/diagrams/floodwatch_defense_ready_core_architecture.svg`
- `files/docs/diagrams/floodwatch_normalized_erd.svg`

This closure record supersedes any older project note that says the real-data Experiment 001 is still blocked or has not been executed.
