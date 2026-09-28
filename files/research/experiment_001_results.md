# FloodWatch Experiment 001 — Real Lokoja Discharge Comparison

Date: 2026-09-28  
Dataset: GRDC station 1834101, River Niger at Lokoja, mean daily discharge.  
Raw GRDC observations are not included in this repository artifact.

## Frozen question
At equivalent warning horizons, does a lightweight data-driven predictor provide a materially better anticipation of high-flow threshold crossings at Lokoja than a calibrated interpretable trend-based warning rule, using only information available up to the forecast date?

## Protocol
- Development domain: 2004-01-01 to 2025-12-31.
- Train: 2004-2014.
- Validation: 2015-2019.
- Final temporal holdout: 2020-2025.
- Primary threshold: training-only Q95 = 18,980.0 m³/s.
- Sensitivity thresholds: training-only Q90 and Q97.5.
- Horizons: 1, 3, 5 and 7 days.
- Long missing gaps are not interpolated.
- B3: interpretable trend extrapolation, with trend window selected on validation only.
- B4: Random Forest using lagged/derived Lokoja discharge history only.
- No rainfall, upstream variables, simulator labels or assumed stage-discharge conversion enter RQ1.
- Final test data are not used for threshold definition or tuning.

## Primary Q95 holdout results

| Horizon | B3 CSI | RF CSI | B3 F1 | RF F1 | B3 FAR | RF FAR | B3 event recall | RF event recall | B3 mean lead | RF mean lead |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 d | 0.500 | 0.500 | 0.667 | 0.667 | 0.400 | 0.400 | 0.750 | 0.750 | 1.00 d | 1.00 d |
| 3 d | 0.727 | 0.667 | 0.842 | 0.800 | 0.111 | 0.200 | 1.000 | 1.000 | 2.00 d | 2.00 d |
| 5 d | 0.533 | 0.522 | 0.696 | 0.686 | 0.000 | 0.400 | 1.000 | 1.000 | 3.25 d | 4.25 d |
| 7 d | 0.409 | 0.455 | 0.581 | 0.625 | 0.250 | 0.483 | 0.750 | 1.000 | 5.33 d | 6.00 d |

## Interpretation
The holdout does not support a general claim that Random Forest materially outperforms B3. At 1 day they tie. At 3 days B3 is stronger and produces fewer false alarms. At 5 days RF provides somewhat earlier warning but with a substantial false-alarm penalty and no CSI/F1 gain. At 7 days RF improves recall and lead time but again at a large false-alarm cost.

Q90 sensitivity favors B3 across the tested horizons. Q97.5 has too few independent events for a strong comparative claim.

## RQ1 conclusion
A simple trend-based rule captures a substantial amount of the useful warning information in local Lokoja discharge history. Random Forest exhibits horizon-specific trade-offs, especially at longer horizons, but the current temporal holdout is too event-sparse and the gains too inconsistent to support a robust material-ML-advantage claim.

This is a valid negative/mixed result, not a failed project.

## Limitation
The 2020-2025 Q95 holdout contains only a small number of independent usable crossing events. Treat Experiment 001 as a minimum decisive undergraduate empirical evaluation, not definitive operational forecast validation.

## Consequence for RQ2
RQ2 remains justified: determine whether hydrologically justified external information, especially upstream Niger/Benue state and basin rainfall, adds enough warning value beyond local discharge history to justify additional complexity.

## Claim boundary
The target is a statistically defined high-flow threshold crossing. It is not an official NIHSA warning threshold, does not establish a permanent stage-discharge conversion, and is not Lokoja field deployment.
