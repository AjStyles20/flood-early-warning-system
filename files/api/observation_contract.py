"""Scientific observation and provenance contract for FloodWatch.

This module is independent of the legacy TelemetryCreate schema. It establishes
vocabulary for physical, historical, derived, external and simulated evidence
without pretending that every source measures the same variables.

It does not implement Experiment 001 or train/serve a research model.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class SourceType(str, Enum):
    LOCAL_SENSOR = "local_sensor"
    AUTHORITATIVE_OBSERVATION = "authoritative_observation"
    GRIDDED_OBSERVATION = "gridded_observation"
    REANALYSIS = "reanalysis"
    MODELLED_EXTERNAL = "modelled_external"
    DERIVED = "derived"
    SIMULATED = "simulated"


class EvidenceClass(str, Enum):
    OBSERVED = "observed"
    OBSERVATION_DERIVED = "observation_derived"
    MODELLED = "modelled"
    DERIVED = "derived"
    SIMULATED = "simulated"


class QualityState(str, Enum):
    VALID = "valid"
    SUSPECT = "suspect"
    MISSING = "missing"
    NOT_MEASURED = "not_measured"
    NOT_APPLICABLE = "not_applicable"
    STALE = "stale"
    INVALID = "invalid"


class ThresholdType(str, Enum):
    OFFICIAL_OPERATIONAL = "official_operational"
    RESEARCH_STATISTICAL = "research_statistical"
    PROTOTYPE_DEMO = "prototype_demo"


class Observation(BaseModel):
    """One hydrometeorological value with enough context to interpret it.

    value=None is intentional for missing/not-measured values. Scientific
    absence must never be silently converted to a numeric zero.
    """

    model_config = {"allow_inf_nan": False, "str_strip_whitespace": True}

    variable: str = Field(min_length=1, max_length=80)
    value: float | None
    unit: str = Field(min_length=1, max_length=40)
    timestamp: datetime
    station_id: str | None = Field(default=None, max_length=100)
    station_name: str | None = Field(default=None, max_length=180)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    spatial_support: str | None = Field(default=None, max_length=240)
    provider: str = Field(min_length=1, max_length=120)
    source_type: SourceType
    evidence_class: EvidenceClass
    quality: QualityState = QualityState.VALID
    source_reference: str | None = Field(default=None, max_length=300)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_value_quality(self):
        absent_states = {
            QualityState.MISSING,
            QualityState.NOT_MEASURED,
            QualityState.NOT_APPLICABLE,
            QualityState.INVALID,
        }
        if self.quality in absent_states and self.value is not None:
            raise ValueError(
                f"quality={self.quality.value} requires value=None; "
                "do not encode unavailable evidence as a numeric value"
            )
        if self.quality not in absent_states and self.value is None:
            raise ValueError(f"quality={self.quality.value} requires a numeric value")
        if (self.lat is None) != (self.lon is None):
            raise ValueError("lat and lon must either both be supplied or both be absent")
        return self


class ThresholdDefinition(BaseModel):
    """A threshold with explicit provenance and scientific status."""

    model_config = {"allow_inf_nan": False, "str_strip_whitespace": True}

    variable: str = Field(min_length=1, max_length=80)
    value: float
    unit: str = Field(min_length=1, max_length=40)
    threshold_type: ThresholdType
    provider: str = Field(min_length=1, max_length=120)
    station_id: str | None = Field(default=None, max_length=100)
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    source_reference: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_period(self):
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("valid_to cannot be earlier than valid_from")
        return self


def unavailable_observation(
    *,
    variable: str,
    unit: str,
    timestamp: datetime,
    provider: str,
    source_type: SourceType,
    evidence_class: EvidenceClass,
    quality: QualityState = QualityState.NOT_MEASURED,
    station_id: str | None = None,
    station_name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Observation:
    """Create an explicit unavailable observation instead of a fake zero."""

    if quality not in {
        QualityState.MISSING,
        QualityState.NOT_MEASURED,
        QualityState.NOT_APPLICABLE,
        QualityState.INVALID,
    }:
        raise ValueError("unavailable_observation requires an absent quality state")

    return Observation(
        variable=variable,
        value=None,
        unit=unit,
        timestamp=timestamp,
        station_id=station_id,
        station_name=station_name,
        provider=provider,
        source_type=source_type,
        evidence_class=evidence_class,
        quality=quality,
        metadata=metadata or {},
    )
