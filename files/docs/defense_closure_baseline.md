# FloodWatch 72-Hour Defense Closure Baseline

Status: ACTIVE CLOSURE PLAN — updated 2026-09-28

This document freezes the minimum defensible product boundary for final completion. It is a closure plan, not a new feature backlog.

## 1. Product claim to defend

FloodWatch is a prototype flood monitoring and decision-support system that accepts source-aware simulated or controlled physical telemetry, validates and persists it, reconstructs current station state from normalized evidence, applies transparent threshold-based risk assessment, records operational alert workflow state, and presents current/historical information through a web dashboard.

The physical prototype demonstrates sensing-to-software integration. It is not claimed as a calibrated Lokoja field gauge. The saved simulator ML is development evidence only.

The separate real-data Lokoja Experiment 001 has now been executed. Its result is negative/mixed: the interpretable B3 trend baseline is highly competitive, while Random Forest shows horizon-specific recall/lead-time gains that often require more false alarms. No general material ML advantage is claimed.

## 2. P0 — must be complete for defense

| Capability | Current evidence | Closure state |
|---|---|---|
| API telemetry ingestion/validation | automated regression + HTTP smoke | PASS |
| Provenance-aware normalized persistence | repository/dual-write tests | PASS |
| MySQL application execution | GitHub Actions MySQL 8.4 integration | PASS |
| Current threshold risk assessment | normalized parity/promotion tests | PASS |
| Historical telemetry read | normalized history test | PASS |
| Dashboard/data pages | API/frontend/smoke tests | PASS |
| Simulator demonstration | existing supported producer | READY |
| Authentication/RBAC/operator workflow | operational tests | PASS |
| Persistent alert workflow/audit | operational tests | PASS |
| Observation identity/integrity constraints | SQLite + MySQL tests | PASS |
| Real Lokoja Experiment 001 | GRDC 1834101 temporal holdout | PASS — mixed/negative ML result |
| Physical Pico after MySQL/read migration | requires user hardware/COM port | PENDING USER-SIDE VALIDATION |
| Final defense demo rehearsal | requires local runtime | PENDING USER-SIDE VALIDATION |
| Final documentation/figure consolidation | synchronized progressively | IN PROGRESS |

## 3. Remaining defense package work

- consolidate Experiment 001 into final Chapter 4/5 results/discussion/conclusion;
- capture final screenshots from the actual local demo;
- rehearse the final demo;
- optionally capture MySQL Workbench/EER screenshots;
- prepare final defense slides and likely viva questions.

## 4. Deferred rather than rushed

- official operational threshold integration;
- field calibration/deployment in Lokoja;
- real SMS/WhatsApp emergency delivery;
- national production deployment;
- authoritative inundation GIS;
- advanced community-reporting workflows;
- destructive DB-5 legacy retirement unless its physical gate passes and retirement is explicitly approved;
- claiming that Random Forest is operationally superior when Experiment 001 does not establish that.

## 5. Frozen defense architecture

```text
Simulator ------------------\
                             -> FastAPI validation -> telemetry service
Pico -> USB serial -> bridge/                         |
                                                       v
                                         normalized MySQL evidence
                                         + compatibility rollback write
                                                       |
                                                       v
                                         threshold current-state engine
                                                       |
                                  +--------------------+-------------------+
                                  v                    v                   v
                             dashboard/data       alert workflow      public API

GRDC Lokoja historical discharge -> separate Experiment 001 research package
```

The saved synthetic model and Experiment 001 are deliberately outside the physical current-state decision path unless a future promotion policy is explicitly justified.

## 6. Stop rule

A feature is not added merely because it is interesting. During closure it must satisfy at least one of these:
- required for the claimed core system to work;
- required to fix a demonstrated defect;
- required to support a thesis claim with evidence;
- required for reproducibility or defense.

Otherwise it becomes future work.

## 7. Current hard blockers

The remaining engineering evidence that cannot be completed remotely is the post-migration physical regression on the user's actual Pico/serial port and local MySQL environment, together with final local screenshots/rehearsal.

Scientific RQ1 is no longer blocked: Experiment 001 has been executed and recorded. RQ2 remains future/extension work unless additional hydrologically justified external datasets are acquired and aligned.

This boundary intentionally favors a smaller working, testable and explainable system over a larger unfinished specification.
