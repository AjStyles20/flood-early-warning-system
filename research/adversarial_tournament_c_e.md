# Adversarial Research Tournament — Candidates C and E

**Date:** 16 September 2026  
**Purpose:** Attack, rather than defend, the two residual directions that appeared promising after the first novelty review.

## Candidate C — Decision-capability graceful degradation

### Candidate formulation attacked
Can a flood early-warning system preserve useful warning capability by deliberately switching among progressively simpler predictors when sensors, network links, or backend services become unavailable?

Example ladder:
1. Full multivariate predictor when level/rain/flow inputs are available.
2. Reduced-feature predictor when one sensor stream disappears.
3. Level + trend predictor when multivariate sensing is unavailable.
4. Local threshold/rate-of-rise warning when remote inference/network service is unavailable.

### Collision findings
Generic fault tolerance, redundant flood sensing, network-outage resilience, and graceful degradation are not novel concepts. They exist in flood-monitoring literature and in adjacent edge-AI/cyber-physical systems. Contemporary edge-AI systems explicitly use adaptive local/cloud inference and report graceful degradation under network outage. Therefore the thesis **cannot** claim novelty merely because FloodWatch continues operating after a sensor or network failure.

### Residual that remains worth testing
The narrower question is not whether fault tolerance exists, but whether a **predefined warning-capability ladder** can maintain quantified flood-warning utility as information sources are removed, and how much warning utility is lost at each degradation state.

This must be evaluated using the same event-level warning metrics as the normal system: CSI/F1, POD/recall, false-alarm ratio, missed events and warning lead time. A resilience ratio may be reported as Utility(degraded) / Utility(full), but the utility definition must be frozen before testing.

### Disposition
**NARROW / SECONDARY EXPERIMENT.**

Do not use C as a standalone first-of-kind novelty claim. It may become a useful robustness experiment or merge with the sensing/complexity question if observational data support it.

---

## Candidate E — Complexity–utility / minimum viable warning configuration

### Candidate formulation attacked
At what point does additional sensing and predictive complexity stop producing meaningful improvement in flood-warning capability in a resource-constrained deployment?

### Strong collision
A 2026 Pareto Data Framework explicitly formalises Minimum Viable Data for resource-constrained edge/IoT machine learning and searches performance-resource trade-offs/knee points. Earlier cost-sensitive sensor-selection and feature-selection literature likewise optimises predictive performance against sensor/feature cost. Consequently, the generic idea of plotting cost/complexity against ML performance and selecting a Pareto-efficient point is **already established**.

### Consequence
The following broad novelty claim is rejected:
> We introduce a novel Pareto/minimum-viable-data framework for balancing sensor cost, computational complexity and prediction accuracy.

FloodWatch did not invent that framework and must not present it as such.

### Residual that remains worth testing
A domain-specific empirical question can remain:
> For impending flood-threshold-crossing warning, what is the smallest physically deployable sensing-and-prediction configuration that retains a predefined fraction of the best observed **warning utility**, including event detection, false alarms and lead time?

The distinction from generic feature selection is important:
- physical sensor configurations, not arbitrary columns only;
- warning utility, not accuracy only;
- strong conventional warning rules included alongside ML;
- deployment cost/resource measurements tied to actual prototype components where possible;
- temporal/event-independent hydrological validation;
- no claim that Pareto optimisation itself is novel.

### Disposition
**NARROW / KEEP AS EMPIRICAL FYP QUESTION.**

Candidate E survives only as a flood-specific empirical evaluation of minimum sufficient deployment complexity. The method is established; the potential contribution would be the independently validated finding, not invention of Pareto optimisation.

---

## Updated tournament board

| Candidate | Current disposition | Role |
|---|---|---|
| A — Is ML worth it versus a strong conventional warning rule? | KEEP | Primary empirical question |
| B — Minimum physically deployable sensing | NARROW / KEEP | Primary or co-primary empirical question |
| C — Decision-capability graceful degradation | NARROW | Secondary robustness experiment |
| D — Cross-basin generalisation | KILL as novelty | Validation stress test only |
| E — Complexity–utility / minimum viable warning configuration | NARROW / KEEP | Integrating analysis for A+B; method itself is not novel |

## Current research core after the kill search

The most defensible programme is no longer a claim that FloodWatch invented IoT flood warning, ML flood prediction, graceful degradation, sensor selection, or Pareto optimisation.

The research core is an **independent empirical evaluation**:

> Determine whether, and under what sensing and computational complexity, lightweight predictive warning provides materially useful improvement over strong conventional threshold/trend warning for impending flood-threshold crossing, and quantify how warning capability changes as sensing/inference resources are reduced.

This formulation is deliberately falsifiable. Possible defensible outcomes include:
- ML materially improves warning utility;
- simple conventional warning is statistically/practically equivalent;
- a reduced sensor set retains most useful performance;
- extra sensors/models provide diminishing returns;
- degradation is abrupt rather than graceful;
- results do not generalise to independent stations/events.

Any of these outcomes can support an undergraduate research contribution if the observational dataset, split protocol, baselines and evaluation are credible.

## Freeze rule

Do **not** convert this residual into a novelty claim yet. It remains a hypothesis programme until:
1. observational hydrological data pass DQR-001;
2. the experimental protocol is frozen before outcome inspection;
3. B3 is implemented as a genuinely strong calibrated conventional baseline;
4. independent temporal/event validation is completed;
5. effect sizes and uncertainty are reported;
6. the final contribution statement is written from the evidence, including a negative result if necessary.
