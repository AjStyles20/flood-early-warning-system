# FloodWatch Research Package

This directory is intentionally separate from the live FastAPI application.

## Purpose

The research package contains reproducible historical-data preparation, the frozen Experiment 001 implementation, and immutable result artefacts for the B3/B4 comparison.

Current status: **Experiment 001 executed on the acquired GRDC Lokoja daily-discharge series on 2026-09-28.**

## Evidence flow

1. source manifest and provenance;
2. raw-data audit;
3. accepted observational series;
4. preprocessing with documented missing-data rules;
5. target construction;
6. temporal/event split;
7. baseline/candidate experiment;
8. evaluation;
9. immutable result artefacts.

## Rules

- Raw GRDC observations are not committed here unless their redistribution terms explicitly permit it.
- No long-gap interpolation is allowed merely to increase sample count.
- Reference-event reports do not silently replace missing time-series observations.
- Stage and discharge are not converted using an assumed permanent relationship.
- Simulator-generated records are development evidence and cannot enter the observational experiment as if they were field observations.
- All transformations used for prediction must be available at prediction time.
- Random row shuffling is not an acceptable validation strategy for the time-series experiment.
- Thresholds are derived from training data only.
- Final test data are not used to tune B3, Random Forest, probability thresholds, or target thresholds.
- This package remains usable without starting the web application.

## Current research site

Scientific focus: River Niger at Lokoja.

Acquired observational source: GRDC station 1834101, mean daily discharge. The source file remains external to the public repository; only provenance/audit metadata, reproducible code, and derived results are committed here.

## Experiment 001

Files:

- `experiment_001.py` — reproducible B3 versus lightweight Random Forest experiment.
- `experiment_001_results.csv` — derived result table.
- `experiment_001_results.md` — protocol, interpretation, limitations and claim boundary.

Primary experimental target: training-defined Q95 high-flow crossing, with Q90 and Q97.5 sensitivity checks.

Temporal partition:

- training: 2004-2014;
- validation: 2015-2019;
- final holdout: 2020-2025.

Primary result: **no robust material Random-Forest advantage was established.** B3 is very competitive, while RF shows horizon-specific recall/lead-time gains that often carry a higher false-alarm cost.

This is a valid negative/mixed RQ1 result and must not be rewritten as “AI proved better.”

## Next research boundary

RQ2 may test whether hydrologically justified upstream Niger/Benue state and basin rainfall add enough useful warning information beyond local Lokoja discharge history to justify additional complexity. Those data are not to be fabricated from the local prototype.

## Reproduction

After obtaining the authorized GRDC daily file:

```powershell
py .\files\research\experiment_001.py --data "C:\path\to\1834101_Q_Day.Cmd.txt" --out experiment_001_results.json
```

The generated JSON should agree with the committed derived CSV within normal deterministic library-version behavior.
