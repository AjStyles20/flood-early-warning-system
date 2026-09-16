# Research Log

## RL-001 — Original concept
FloodWatch conceived as an AI/IoT flood early-warning and decision-support system.

## RL-002 — Prototype development
Core simulator, FastAPI backend, persistence/risk processing, ML components, dashboard and alerts developed.

## RL-003 — Physical integration
Raspberry Pi Pico physical telemetry integrated through COM4 -> Python serial bridge -> FastAPI `/api/telemetry` -> dashboard.

## RL-004 — Repository audit
Repository reproducibility and API/authentication consistency issues identified for later engineering remediation.

## RL-005 — Novelty review initiated
Broad IoT + ML + GIS/dashboard + alert novelty challenged against academic, operational and open-source prior art.

## RL-006 — Broad novelty rejected
Related global and Nigerian systems identified. Architecture alone cannot support a first-of-kind claim.

## RL-007 — Contribution tournament
Candidate directions examined: ML versus conventional warning, sensor/input minimisation, graceful degradation, cross-basin generalisation, complexity/utility trade-offs and warning continuity.

## RL-008 — Candidate collisions
Broad claims around sensor optimisation, transfer/generalisation, fault tolerance, graceful degradation and forecast utility found to be established or materially occupied.

## RL-009 — Residual direction
Narrow empirical/systems programme retained: test whether additional predictive and sensing complexity provides materially useful warning benefit over strong conventional warning under independently validated conditions.

## RL-010 — Research Contribution Contract
RQ1–RQ4, baseline philosophy, evaluation, evidence separation, falsification and pivot rules frozen as v1.0.

## RL-011 — NIHSA acquisition
16 September 2026: academic hydrological-data request submitted for Lokoja, Makurdi and relevant Niger/Benue monitoring locations.

## RL-012 — GRDC acquisition
16 September 2026: GRDC discharge requested for Station 1834101, LOKOJA, RIVER NIGER, Nigeria. Request ID **87616**. Portal showed daily availability 1914–2007 and monthly availability 1914–2012. Awaiting delivery.

## RL-013 — Formal research baseline
16 September 2026: Research Baseline v1.0 established. Documentation/provenance workflow initiated. Next scientific gate: DQR-001 after first observational dataset arrives.

## RL-014 — Hard kill search on graceful degradation and complexity–utility
16 September 2026: Candidate C and Candidate E attacked against flood and adjacent-domain prior art. Generic graceful degradation/fault tolerance is established; C narrowed to a quantified warning-capability degradation experiment. Generic Pareto/cost-performance/minimum-viable-data optimisation is also established; E narrowed to a flood-specific empirical question about the smallest physically deployable sensing-and-prediction configuration that preserves predefined warning utility. No novelty claim frozen. Detailed record: `research/adversarial_tournament_c_e.md`.
