# Dataset and Acquisition Register

## DS-001 — GRDC Lokoja discharge
- Provider: Global Runoff Data Centre (GRDC)
- Station: LOKOJA
- Station ID: 1834101
- River: RIVER NIGER
- Country: Nigeria
- Request date: 16 September 2026
- Request ID: **87616**
- Availability shown at request time: daily 1914–2007; monthly 1914–2012
- Status: REQUESTED / AWAITING DOWNLOAD
- Intended role: observational discharge qualification and potential primary/backup real-data validation
- Handling rule: preserve delivered original unchanged; record filename, retrieval date, provider metadata, native frequency and SHA-256 before processing

## DS-002 — NIHSA academic hydrological data
- Provider: Nigeria Hydrological Services Agency (NIHSA)
- Request date: 16 September 2026
- Requested locations: Lokoja, Makurdi and relevant Niger/Benue monitoring stations
- Requested variables where available: timestamp, water level/stage, discharge, rainfall, warning/danger/flood thresholds, event information, station metadata and units
- Status: REQUESTED / AWAITING RESPONSE
- Intended role: preferred Nigeria-specific observational evidence and threshold/station metadata
- Handling rule: preserve delivered originals unchanged and document all provider conditions

## Planned complementary sources
- DS-003: CHIRPS precipitation, only if required and spatially/temporally justified
- DS-004: GloFAS/reanalysis discharge, as reproducible fallback/external evidence where observational coverage is insufficient

## Raw-data rule
Never overwrite or manually clean the only copy of a provider-delivered dataset. Derived cleaning, harmonisation, target construction and feature engineering belong in separate processed/interim artefacts with reproducible scripts.
