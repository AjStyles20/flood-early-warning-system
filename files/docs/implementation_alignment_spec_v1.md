# FloodWatch Implementation Alignment Specification v1.0

Status: implementation baseline before controlled refactor.

## 1. Purpose

FloodWatch is an engineering prototype and research testbed for flood early-warning decision support. The application must keep scientific evidence, controlled simulation, and physical prototype measurements distinguishable.

This specification does not change the thesis or authorize Experiment 001. It translates the current research decisions into software constraints.

## 2. Core rule

No variable, sensor, model, threshold, warning rule, external data source, or application feature enters the core FloodWatch decision path merely because it is technically available. It must have a defined hydrological or engineering purpose, known provenance, and evidence appropriate to the claim being made.

## 3. Four software planes

### Observation plane
Acquires and standardizes evidence from physical sensors, authoritative observations, gridded observations, reanalysis/modelled sources, derived variables, and simulation.

### Research plane
Handles historical-data audit, preprocessing, target construction, temporal/event validation, baselines, candidate models, ablation and evaluation. Research code is separate from the live API. Experiment 001 remains blocked until its protocol is explicitly released.

### Decision plane
Converts current observations and, only when validated, forecast outputs into decision-support states. Current state, forecast probability, and operational warning state are different concepts and must not be silently placed on one numeric scale.

### Presentation/action plane
Displays evidence, provenance, freshness, warning state and alerts. It must not make simulated, modelled or placeholder data appear observational.

## 4. Variable semantics

A variable must be classified by role where applicable:
- cause/driver: contributes physically to flood generation;
- catchment control: affects how drivers become runoff/river response;
- hydrological response: observed river-system response such as stage/discharge;
- predictor: information legitimately available at prediction time;
- target: future event the experiment is defined to anticipate;
- warning variable: evidence used by an operational warning rule;
- contextual variable: static/supporting information not treated as a time-varying predictor.

A variable may have more than one role, but the role must be explicit in each use.

## 5. Minimum observation contract

Every scientific observation should be able to preserve:
- variable name;
- value and unit;
- observation/event timestamp;
- location/station identity and spatial support where relevant;
- source/provider;
- source type/evidence class;
- quality state;
- whether the value was measured, modelled, derived or simulated;
- optional source-specific metadata.

Unavailable is not zero. A missing rainfall or discharge measurement must not be encoded as 0.0 merely to satisfy an API shape.

## 6. Provenance classes

Initial software vocabulary:
- local_sensor: direct physical prototype measurement;
- authoritative_observation: observational record from a recognized data provider/gauge archive;
- gridded_observation: spatially gridded observation-derived product;
- reanalysis: reconstructed/model-assimilated environmental dataset;
- modelled_external: externally modelled hydrological/environmental value;
- derived: calculated from one or more identified source observations;
- simulated: generated for controlled software/scenario testing.

The source provider (for example GRDC) is separate from source type.

## 7. Current accepted scientific roles

### Lokoja discharge
GRDC station 1834101 daily mean discharge is acquired observational evidence and is suitable for raw-data/event viability work. It is not automatically an official flood-warning threshold.

### River stage
Scientifically relevant local hydrological response/warning variable when a valid stage series and threshold are available. The current potentiometer is only a controlled analogue input emulating stage-like change; it is not a Lokoja field measurement.

### Trend/rate of change
Derived variable. Its provenance must point to the underlying observation series and its time interval.

### Rainfall
Potential driver/predictor. Local rainfall and catchment/upstream rainfall are not interchangeable. Catchment rainfall must not be added until its spatial support is justified.

### Upstream conditions
Potentially important predictors/context for Lokoja because it lies within the Niger-Benue system. They must not be fabricated or represented by an arbitrary local sensor.

### Soil moisture, reservoir releases and other variables
Excluded from the core path unless the evidence gate and obtainable data justify them for the defined experiment.

## 8. Threshold rules

A threshold must carry provenance and type. At minimum the system must be able to distinguish:
- official/operational threshold;
- research/statistical threshold;
- prototype/demo threshold.

A prototype threshold must never be presented as an official Lokoja threshold.

Stage and discharge thresholds must not be converted using an assumed permanent fixed relationship.

## 9. Missingness and quality

Missing, not measured, not applicable, stale and invalid are distinct states.

Rules:
1. Do not replace unavailable scientific variables with zero.
2. Do not interpolate long observational gaps to manufacture evidence.
3. Do not silently substitute an independent event-reference value into a missing time-series observation.
4. Derived values inherit provenance/quality constraints from their inputs.
5. Dashboard/API outputs should expose source and quality where decisions depend on them.

## 10. Simulator role

Permitted:
- API integration testing;
- dashboard testing;
- controlled rising/falling scenarios;
- alert workflow testing;
- missing-data/fault scenarios;
- reproducible software tests.

Not permitted as evidence for:
- real Lokoja predictive accuracy;
- real false-alarm rate;
- real warning lead time;
- hydrological generalization;
- superiority of ML over conventional warning.

Illustrative station coordinates/thresholds must remain visibly simulated and must not be described as authoritative Nigerian operational gauges.

## 11. Physical prototype role

The Pico/serial/API pipeline demonstrates physical sensing-to-software integration. Until a calibrated environmental sensor is deployed, the potentiometer is a controlled analogue input, not a water-level observation.

Physical validation may demonstrate acquisition, transmission, persistence, failure handling and dashboard response. It does not by itself validate historical Lokoja predictive performance.

## 12. Historical research pipeline

Historical research data must be handled outside the live application path:

raw source -> manifest/provenance -> raw-data audit -> accepted observations -> preprocessing -> target construction -> temporal/event split -> experiment -> evaluation -> result artefacts.

GRDC raw data must be handled according to its data-sharing conditions; repository code should not assume raw redistribution is allowed.

## 13. Research-to-application promotion rule

An experimental method may enter the operational decision path only after:
1. its target and horizon are documented;
2. its input variables are available at prediction time;
3. its provenance is known;
4. its validation split is independent and appropriate;
5. its performance is compared with the agreed baseline;
6. failure/limitations are documented;
7. the resulting warning policy is explicitly defined.

Until then, experimental models remain research/development artefacts.

## 14. Current implementation disposition

KEEP:
- FastAPI foundation;
- persistence foundation;
- authentication/roles;
- dashboard and alert infrastructure;
- Pico serial transport/bridge;
- simulator as controlled-test infrastructure;
- existing tests that verify engineering behavior.

REFACTOR:
- telemetry schema/data contract;
- source/provenance representation;
- placeholder-zero semantics;
- risk-engine combination of threshold ratio and ML probability;
- dashboard wording/provenance;
- simulator identity/illustrative station metadata;
- large main.py responsibility boundaries.

FREEZE AS DEVELOPMENT EVIDENCE:
- model.pkl;
- model_metrics.json;
- current synthetic Random Forest serving path;
- synthetic train_model.py results.

NEW, BUT NOT YET EXPERIMENT EXECUTION:
- observation/provenance schema;
- historical-data adapters/manifests;
- research package boundary;
- raw-data audit utilities;
- later B3/B4/evaluation modules only after protocol release.

## 15. Refactor order

1. Define observation/provenance contract without breaking current telemetry.
2. Make unavailable scientific measurements representable without fabricated zeroes.
3. Add explicit threshold provenance/type.
4. Adapt physical bridge and simulator to the contract.
5. Preserve backward compatibility while tests are migrated.
6. Separate current-state assessment from forecast/model output.
7. Split API responsibilities gradually.
8. Build historical research ingestion/audit layer.
9. Stop and review before implementing Experiment 001.

## 16. Test gate

Before Experiment 001, the refactored engineering system must demonstrate:
- legacy telemetry can still be ingested during migration;
- physical bridge payload is accepted without fake rainfall/flow values;
- simulated evidence remains visibly simulated;
- provenance and threshold type survive storage/API round trips;
- current-state warning works without an ML model;
- absence of a model is a supported state;
- no test labels simulator results as real Lokoja evidence.

This document is the implementation contract for the next controlled refactor.
