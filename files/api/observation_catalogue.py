"""Controlled catalogue values for the normalized observation model.

These catalogues define representation/provenance vocabulary only.  They do
not claim that every variable/source is currently measured or belongs in every
FloodWatch research experiment.
"""

VARIABLE_CATALOGUE = (
    {"code": "river_stage", "name": "River stage / water level", "unit": "m", "category": "hydrological"},
    {"code": "river_discharge", "name": "River discharge", "unit": "m3/s", "category": "hydrological"},
    {"code": "rainfall_rate", "name": "Rainfall rate", "unit": "mm/h", "category": "meteorological"},
    {"code": "rainfall_total", "name": "Accumulated rainfall", "unit": "mm", "category": "meteorological"},
    {"code": "rate_of_rise", "name": "Rate/change of river level", "unit": "contextual", "category": "derived"},
    {"code": "battery_pct", "name": "Device battery percentage", "unit": "%", "category": "operational"},
)

SOURCE_CATALOGUE = (
    {
        "code": "LOCAL_SENSOR",
        "name": "Local physical monitoring node",
        "evidence_type": "observed",
        "provider": "FloodWatch prototype",
        "notes": "Physical/local observation source. Sensor calibration and field validity remain separate evidence questions.",
    },
    {
        "code": "AUTHORITATIVE_OBSERVATION",
        "name": "Authoritative hydrological observation",
        "evidence_type": "observed",
        "provider": None,
        "notes": "Provider and dataset metadata must identify the actual authority for each imported dataset.",
    },
    {
        "code": "GRIDDED_OBSERVATION",
        "name": "Gridded observational product",
        "evidence_type": "observed",
        "provider": None,
        "notes": "External gridded observational evidence; dataset provenance remains mandatory.",
    },
    {
        "code": "REMOTE_SENSING",
        "name": "Remote-sensing product",
        "evidence_type": "observed",
        "provider": None,
        "notes": "Satellite/remote-sensing evidence; product-specific limitations must be retained.",
    },
    {
        "code": "REANALYSIS",
        "name": "Reanalysis product",
        "evidence_type": "reanalysis",
        "provider": None,
        "notes": "Model/observation assimilation product; must not be silently labelled as direct gauge observation.",
    },
    {
        "code": "MODELLED_EXTERNAL_DATA",
        "name": "External model output",
        "evidence_type": "modelled",
        "provider": None,
        "notes": "External modelled evidence; model identity and provenance are required.",
    },
    {
        "code": "DERIVED",
        "name": "Derived FloodWatch variable",
        "evidence_type": "derived",
        "provider": "FloodWatch",
        "notes": "Computed from other evidence; derivation method must remain reproducible.",
    },
    {
        "code": "SIMULATED",
        "name": "Controlled simulator",
        "evidence_type": "simulated",
        "provider": "FloodWatch",
        "notes": "Development/demonstration evidence only; never presented as field observation.",
    },
)
