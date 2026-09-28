# Chapter Four Draft — Results, Evaluation and Discussion

## 4.1 Introduction

This chapter reports the verified engineering results of FloodWatch and the real-data observational evaluation used to answer the narrowed research question. The engineering prototype and the historical hydrological experiment are reported separately because they use different evidence and support different claims.

The prototype demonstrates source-aware sensing-to-software integration, persistent storage, threshold-state assessment, dashboard presentation and alert workflow. The observational experiment evaluates whether a lightweight Random Forest provides materially better early warning of future high-flow threshold crossings than an interpretable trend-based rule using real daily discharge observations from the River Niger at Lokoja.

## 4.2 Engineering Verification Summary

The implemented platform supports:

- simulated and controlled physical telemetry ingestion through FastAPI;
- provenance-aware observation handling;
- normalized MySQL-capable persistence with SQLite test compatibility;
- current-state threshold assessment;
- historical reads;
- dashboard/data pages;
- authentication and role-aware operator functions;
- persistent alert workflow and audit;
- Pico-to-serial-bridge-to-API integration previously demonstrated.

These engineering results establish that FloodWatch exists as a functioning prototype. They do not by themselves establish predictive skill for real Lokoja floods.

The post-migration physical Pico regression and final local MySQL/dashboard screenshots remain user-side validation tasks because they require the actual serial port, hardware and local runtime.

## 4.3 Observational Dataset

Experiment 001 uses the acquired GRDC station 1834101 series for the River Niger at Lokoja. The file is mean daily discharge and spans a long historical period. The experiment deliberately uses the modern 2004–2025 block for the primary comparative protocol because it provides comparatively high completeness while preserving a genuinely later temporal holdout.

Raw GRDC observations are not committed to the public repository. Only provenance, reproducible experiment code and derived result artefacts are stored.

## 4.4 Experimental Target

The experiment does not claim an official discharge flood-warning threshold. Instead, it defines a high-flow threshold from the training data only.

Primary boundary:

Q95(training) = 18,980.0 m³/s

For each eligible day t below the boundary, the target asks whether discharge crosses the boundary within H future days, where H is 1, 3, 5 or 7 days.

Q90 and Q97.5 are retained as sensitivity boundaries.

Long missing gaps are not interpolated, and rows requiring unavailable current, lagged or future verification observations are excluded.

## 4.5 Temporal Design

The frozen split is:

- Training: 2004–2014
- Validation: 2015–2019
- Final test holdout: 2020–2025

The final test block is not used to set the high-flow threshold, select the B3 trend window, fit the Random Forest, or select the Random Forest probability cutoff.

This chronological split prevents the random-row leakage that would occur if neighbouring hydrological observations from the same flood evolution were distributed across training and testing.

## 4.6 Compared Methods

### 4.6.1 B3 Interpretable Trend Baseline

B3 extrapolates recent observed discharge trend toward the future horizon. Its trend window is selected using validation data only.

The purpose of B3 is to provide a serious low-complexity competitor rather than a deliberately weak baseline.

### 4.6.2 B4 Lightweight Random Forest

B4 is a Random Forest classifier using only information derived from Lokoja discharge history available up to prediction time. Inputs include current/lagged discharge, recent rate-of-change and short rolling summaries.

For RQ1, the model does not receive rainfall, upstream Niger/Benue measurements, soil moisture, simulator-generated labels or an assumed stage-discharge conversion.

## 4.7 Primary Q95 Results

| Horizon | B3 CSI | RF CSI | B3 F1 | RF F1 | B3 FAR | RF FAR | B3 event recall | RF event recall | B3 mean lead | RF mean lead |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 day | 0.500 | 0.500 | 0.667 | 0.667 | 0.400 | 0.400 | 0.750 | 0.750 | 1.00 d | 1.00 d |
| 3 days | 0.727 | 0.667 | 0.842 | 0.800 | 0.111 | 0.200 | 1.000 | 1.000 | 2.00 d | 2.00 d |
| 5 days | 0.533 | 0.522 | 0.696 | 0.686 | 0.000 | 0.400 | 1.000 | 1.000 | 3.25 d | 4.25 d |
| 7 days | 0.409 | 0.455 | 0.581 | 0.625 | 0.250 | 0.483 | 0.750 | 1.000 | 5.33 d | 6.00 d |

## 4.8 Discussion of RQ1

The results do not establish a general material advantage for Random Forest.

At the one-day horizon the methods tie on the reported primary point metrics and event recall.

At three days B3 has the stronger CSI and F1 and the lower false-alarm ratio while achieving the same event recall and mean lead time.

At five days Random Forest detects more positive prediction points and increases mean lead time, but the gain is accompanied by a much higher false-alarm ratio. B3 retains slightly stronger CSI and F1.

At seven days Random Forest improves CSI, F1, event recall and mean lead time. However, the false-alarm ratio increases from 0.250 for B3 to 0.483 for Random Forest.

Therefore, the ML method exhibits a trade-off rather than a uniform improvement. The extra complexity can increase warning reach at longer horizons, but on this holdout it often buys that gain by producing more false warnings.

## 4.9 Sensitivity Results

The training-only Q90 sensitivity tests favour B3 across the tested horizons. Q97.5 contains very few independent high-flow events in the final holdout, so apparent differences at that boundary are too fragile for a strong conclusion.

The lack of consistent Random-Forest dominance across threshold definitions reinforces the decision not to describe the result as “AI is better.”

## 4.10 Event-Level Limitation

Future-crossing prediction points are not independent flood events. Several positive days can refer to the same high-flow episode.

The final Q95 holdout contains only a small number of independent usable crossing events. This limits statistical certainty and makes the experiment a minimum decisive undergraduate evaluation rather than definitive operational validation.

This limitation is reported directly rather than hidden by row-level accuracy.

## 4.11 Implication for the FloodWatch Architecture

The result supports retaining the interpretable threshold/current-state engine as the operational default.

Experiment 001 does not justify replacing that engine with the Random Forest.

The predictive research package therefore remains separated from the live application. A later promotion would require stronger evidence, an explicit operational threshold relationship and external validation.

## 4.12 RQ2 Direction

The supervisor's hydrological concern remains important. RQ1 intentionally tests how much warning is available from local river-state history alone.

A logical RQ2 is therefore to test whether hydrologically justified external variables, particularly upstream Niger/Benue conditions and basin rainfall, add enough warning value to improve lead time or event detection without an unacceptable false-alarm cost.

This question should only be tested after trustworthy external datasets are acquired and aligned. Additional physical sensors are not added merely to increase feature count.

## 4.13 Chapter Summary

FloodWatch is a functioning engineering prototype, and the first real-data observational experiment has been completed.

The principal scientific result is negative/mixed rather than promotional: local discharge history already supports a strong interpretable warning rule, while Random Forest shows selective longer-horizon benefits that are not consistent enough to establish a robust material advantage.

This result answers the narrowed RQ1 without requiring machine learning to win.
