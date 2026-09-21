"""Dataset provenance manifest types for FloodWatch research.

This module records what a dataset is before any modelling occurs. It performs
no training, threshold selection, interpolation or Experiment 001 work.
"""

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class DatasetEvidenceType(str, Enum):
    OBSERVATIONAL = "observational"
    GRIDDED_OBSERVATION = "gridded_observation"
    REANALYSIS = "reanalysis"
    MODELLED = "modelled"
    SIMULATED = "simulated"


class RedistributionStatus(str, Enum):
    ALLOWED = "allowed"
    RESTRICTED = "restricted"
    UNKNOWN = "unknown"


class DatasetManifest(BaseModel):
    dataset_id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=240)
    provider: str = Field(min_length=1, max_length=120)
    evidence_type: DatasetEvidenceType
    variable: str = Field(min_length=1, max_length=100)
    unit: str = Field(min_length=1, max_length=40)
    station_or_spatial_support: str = Field(min_length=1, max_length=300)
    temporal_resolution: str = Field(min_length=1, max_length=80)
    coverage_start: date | None = None
    coverage_end: date | None = None
    acquired_at: datetime | None = None
    source_reference: str | None = Field(default=None, max_length=500)
    redistribution: RedistributionStatus = RedistributionStatus.UNKNOWN
    raw_file_committed: bool = False
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_manifest(self):
        if self.coverage_start and self.coverage_end and self.coverage_end < self.coverage_start:
            raise ValueError("coverage_end cannot be earlier than coverage_start")
        if self.redistribution == RedistributionStatus.RESTRICTED and self.raw_file_committed:
            raise ValueError("restricted raw data must not be marked as committed")
        return self


GRDC_LOKOJA_DAILY = DatasetManifest(
    dataset_id="GRDC-1834101-Q-DAY",
    title="River Niger at Lokoja - Mean Daily Discharge",
    provider="GRDC",
    evidence_type=DatasetEvidenceType.OBSERVATIONAL,
    variable="river_discharge",
    unit="m3/s",
    station_or_spatial_support="GRDC station 1834101, River Niger at Lokoja, Nigeria",
    temporal_resolution="daily",
    coverage_start=date(1914, 10, 1),
    coverage_end=date(2026, 1, 13),
    redistribution=RedistributionStatus.RESTRICTED,
    raw_file_committed=False,
    notes=(
        "Acquired source used for the raw-data/event viability gate. "
        "Known missing periods must remain explicit. No permanent stage-discharge "
        "conversion is assumed."
    ),
)
