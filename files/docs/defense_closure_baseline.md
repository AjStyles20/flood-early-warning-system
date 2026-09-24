# FloodWatch 72-Hour Defense Closure Baseline

Status: ACTIVE CLOSURE PLAN — 2026-09-24

This document freezes the minimum defensible product boundary for the final three-day completion window. It is a closure plan, not a new feature backlog.

## 1. Product claim to defend

FloodWatch is a prototype flood monitoring and decision-support system that accepts source-aware simulated or controlled physical telemetry, validates and persists it, reconstructs current station state from normalized evidence, applies transparent threshold-based risk assessment, records operational alert workflow state, and presents current/historical information through a web dashboard.

The physical prototype demonstrates sensing-to-software integration. It is not claimed as a calibrated Lokoja field gauge. The saved simulator ML is development evidence only. The real Lokoja research experiment remains scientifically separate until its protocol is frozen and executed.

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
| Physical Pico after MySQL/read migration | requires user hardware/COM port | PENDING |
| Final defense demo rehearsal | requires local runtime | PENDING |
| Final documentation/figure consolidation | progressively synchronized | IN PROGRESS |

## 3. P1 — complete if it improves defense after P0

- real Lokoja B3 versus lightweight-ML experiment, only after protocol freeze;
- final screenshots from the actual local demo;
- final Chapter 4/5 results/discussion/conclusion consolidation;
- defense slides and likely viva questions;
- local MySQL Workbench screenshots/EER inspection.

## 4. Deferred rather than rushed

- official operational threshold integration;
- field calibration/deployment in Lokoja;
- real SMS/WhatsApp emergency delivery;
- national production deployment;
- authoritative inundation GIS;
- advanced community-reporting workflows;
- destructive DB-5 legacy retirement unless its physical gate passes and retirement is explicitly approved;
- any new model training presented as real-world flood skill without the observational experiment.

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
```

The saved synthetic model is deliberately outside the physical current-state decision path.

## 6. Three-day execution order

### Day 1 — freeze engineering
1. Run/maintain full CI green.
2. Remove stale documentation that contradicts the current MySQL/normalized architecture.
3. Freeze P0 software surface; only fix defects affecting core demonstration or evidence integrity.
4. Prepare exact local MySQL + API + bridge commands.

### Day 2 — prove the vertical system
1. Run Pico -> serial -> bridge -> FastAPI -> MySQL -> normalized read -> dashboard.
2. Record verifier output, HTTP 200 evidence, risk-status output and screenshots.
3. If the research protocol is frozen, execute the minimum defensible observational experiment. Do not substitute simulator metrics.
4. Fix only failures found in the vertical regression.

### Day 3 — package and rehearse
1. Consolidate implementation/design documentation and figure numbering.
2. Produce results/discussion/limitations from evidence actually obtained.
3. Run final automated regression.
4. Rehearse primary demo and simulator fallback.
5. Prepare defense slides/script and likely technical questions.

## 7. Stop rule

A feature is not added merely because it is interesting. During closure it must satisfy at least one of these:
- required for the claimed core system to work;
- required to fix a demonstrated defect;
- required to support a thesis claim with evidence;
- required for reproducibility or defense.

Otherwise it becomes future work.

## 8. Current hard blockers

The remaining engineering blocker that cannot be completed remotely is the post-migration physical regression on the user's actual Pico/serial port and local MySQL environment. Scientific model claims remain blocked until the real observational protocol/results exist.

This boundary intentionally favors a smaller working, testable and explainable system over a larger unfinished specification.
