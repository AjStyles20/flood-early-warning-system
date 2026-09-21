# FloodWatch Research Package

This directory is intentionally separate from the live FastAPI application.

## Purpose

The research package will contain reproducible historical-data preparation and, only after the experiment protocol is released, the B3/B4 comparison and evaluation.

Current status: **pre-experiment scaffold only**. Experiment 001 is not authorized by this directory.

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
- Threshold and horizon choices must be frozen by the experiment protocol before final evaluation.
- This package must remain usable without starting the web application.

## Current research site

Scientific focus: River Niger at Lokoja.

Acquired observational source: GRDC station 1834101, mean daily discharge. The source file remains external to the public repository; only provenance/audit metadata and reproducible code should be committed here.

## Not yet implemented

The following are deliberately absent until the experiment-design gate authorizes them:

- B3 baseline implementation;
- B4/Random Forest training;
- threshold selection;
- final horizon selection;
- final temporal/event split;
- model comparison;
- thesis-result generation.
