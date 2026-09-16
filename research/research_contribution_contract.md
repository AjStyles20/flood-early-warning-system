# Research Contribution Contract v1.0

Date frozen: 16 September 2026

## Research identity
FloodWatch is an experimental flood early-warning and decision-support testbed. The intended contribution is empirical and systems-oriented, not a claim to a new ML algorithm or first-of-kind IoT/AI flood system.

## Research questions
**RQ1.** Does a lightweight ML warning model provide a statistically and operationally meaningful improvement over a calibrated threshold-and-trend baseline for future flood/high-flow threshold crossings?

**RQ2.** How does warning performance change as legitimate hydrometeorological inputs are added or removed?

**RQ3.** Does any observed ML advantage persist across warning horizons and independent temporal/event validation, and across an unseen station/basin if suitable data permit?

**RQ4 (secondary).** How much warning capability is retained under controlled sensing or communication degradation?

## Hypothesis philosophy
H0: ML does not provide a practically meaningful warning improvement over the strong conventional baseline.

H1: ML provides a practically meaningful warning improvement.

The minimum practically meaningful difference must be defined before final test-set evaluation.

## Comparator hierarchy
- B0: reactive/current threshold reference
- B1: persistence
- B2: rate-of-rise/trend
- B3: calibrated strong conventional anticipatory warning baseline
- B4: lightweight data-driven predictor; Logistic Regression and Random Forest are initial candidates

B3 must not be intentionally weakened to make B4 look superior.

## Target
When the current hydrological state is below the documented threshold T, predict whether the threshold will be crossed within future horizon H. H must respect the dataset's native temporal resolution.

## Evaluation
Primary: CSI and event-level F1.
Secondary: POD/recall, false-alarm ratio, precision, missed events, warning lead time, and probabilistic calibration where applicable. Resource requirements may include inference latency, model size and required inputs.

## Validation rules
- No random row shuffle for decisive hydrological validation.
- Prefer temporal/event holdout; external station/basin validation if data permit.
- Calibration, scaling, threshold selection and feature construction use training/development data only.
- No future information may enter predictors.

## Evidence separation
Real observational/reanalysis hydrology establishes predictive evidence. Simulation establishes controlled scenario/fault evidence. Physical hardware establishes implementation feasibility.

## Explicit non-claims
The project does not claim to invent IoT flood monitoring, ML flood prediction, Random Forest flood prediction, GIS/dashboard flood warning, SMS/web alerts, feature selection, cross-basin generalisation, fault tolerance, or forecast-value evaluation. It does not currently claim to be the first Nigerian AI/IoT flood-warning system.

## Falsification
The ML claim is unsupported if its apparent advantage is not material, disappears under independent validation, requires unacceptable false alarms, provides no useful lead-time gain, collapses on observational data, or exists only on simulator-generated data.

Negative results remain valid research findings.

## Pivot triggers
Synthetic-to-real collapse, sensor redundancy, horizon dependence, spatial generalisation collapse, failure sensitivity, or strong conventional-baseline dominance may justify a new hypothesis. A trigger does not automatically establish novelty; prior art must be checked before a pivot is adopted.

## Success condition
The project succeeds academically by answering the research questions rigorously with independent evidence and by demonstrating the supported warning strategy in the physical FloodWatch testbed. ML is not required to win.
