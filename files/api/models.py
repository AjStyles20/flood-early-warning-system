# models.py

# This file defines the "shape" or structure of our data. 
# It handles two entirely different but closely related tasks:
# 1. SQLAlchemy Models: Defines how data is physically stored in the configured relational DBMS.
# 2. Pydantic Models: Defines how we validate data when it arrives from the internet, ensuring it is correct before saving it.

from sqlalchemy import Boolean, CheckConstraint, Column, Integer, String, Float, DateTime, ForeignKey, Index, Text
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime, timezone
from typing import Literal

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(80), nullable=False)
    last_name = Column(String(80), nullable=False)
    email = Column(String(160), unique=True, index=True, nullable=False)
    # Phone number supports SMS-capable contact for users who may not rely on
    # smartphones. It is nullable so existing prototype accounts remain valid
    # after migration, but new registration forms require it.
    phone_number = Column(String(32), nullable=True)
    password_hash = Column(String(255), nullable=False)
    # Roles support the expanded operational dashboard:
    # - viewer/user: can view public/core pages and personal settings.
    # - operator: can upload telemetry CSVs, run scenarios, and manage alerts.
    # - admin: can do operator work and manage user roles.
    role = Column(String(32), default="user", nullable=False)
    preferred_language = Column(String(8), default="en", nullable=False)
    email_updates = Column(Boolean, default=True, nullable=False)
    sms_updates = Column(Boolean, default=True, nullable=False)
    # WhatsApp is saved only as a future/channel preference. The active system
    # must not claim real WhatsApp delivery until a provider is configured and
    # tested.
    whatsapp_updates = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)


class CommunityReport(Base):
    __tablename__ = "community_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(140), nullable=False)
    location = Column(String(160), nullable=False)
    message = Column(String(1200), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class AlertEvent(Base):
    """Persistent alert item that operators can acknowledge/escalate/resolve.

    The older prototype wrote alert information only to JSONL logs. This table
    adds an auditable workflow while still keeping the alert wording
    decision-support focused instead of autonomous command language.
    """

    __tablename__ = "alert_events"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(String(64), index=True, nullable=False)
    station_name = Column(String(160), nullable=False)
    data_source = Column(String(24), nullable=False, index=True)
    risk_level = Column(String(32), nullable=False, index=True)
    message = Column(Text, nullable=False)
    channels_json = Column(Text, nullable=False, default="{}")
    status = Column(String(32), nullable=False, default="new", index=True)
    operator_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    acknowledged_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    escalated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    escalated_at = Column(DateTime, nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)


class AlertAuditLog(Base):
    """Append-only record of operator alert-status changes."""

    __tablename__ = "alert_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(Integer, ForeignKey("alert_events.id"), nullable=False, index=True)
    action = Column(String(64), nullable=False)
    from_status = Column(String(32), nullable=True)
    to_status = Column(String(32), nullable=False)
    notes = Column(Text, nullable=True)
    operator_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    operator_email = Column(String(160), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)


class ScenarioRun(Base):
    """Record of operator-triggered demonstration or evaluation scenarios."""

    __tablename__ = "scenario_runs"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(String(64), nullable=False, index=True)
    station_name = Column(String(160), nullable=False)
    scenario = Column(String(32), nullable=False)
    before_risk = Column(String(32), nullable=False)
    after_risk = Column(String(32), nullable=False)
    before_water_level_m = Column(Float, nullable=False)
    after_water_level_m = Column(Float, nullable=False)
    operator_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    operator_email = Column(String(160), nullable=False)
    metrics_snapshot_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

# ==============================================================================
# NORMALIZED OBSERVATION / PROVENANCE MODEL
# These tables are introduced alongside the legacy telemetry table. They do not
# delete or replace the proven Pico/simulator compatibility path yet.
# ==============================================================================

class Station(Base):
    __tablename__ = "stations"
    __table_args__ = (
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_stations_latitude"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="ck_stations_longitude"),
    )

    id = Column(Integer, primary_key=True, index=True)
    station_code = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(160), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    station_type = Column(String(64), nullable=False, default="monitoring")
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class Variable(Base):
    __tablename__ = "variables"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(160), nullable=False)
    unit = Column(String(32), nullable=False)
    category = Column(String(64), nullable=False)
    active = Column(Boolean, nullable=False, default=True)


class DataSource(Base):
    __tablename__ = "data_sources"
    __table_args__ = (
        CheckConstraint(
            "evidence_type IN ('observed', 'derived', 'simulated', 'reanalysis', 'modelled')",
            name="ck_data_sources_evidence_type",
        ),
        CheckConstraint(
            "(is_observational = 1 AND evidence_type = 'observed') OR "
            "(is_observational = 0 AND evidence_type <> 'observed')",
            name="ck_data_sources_observational_consistency",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(160), nullable=False)
    evidence_type = Column(String(64), nullable=False, index=True)
    provider = Column(String(160), nullable=True)
    is_observational = Column(Boolean, nullable=False, default=False)
    notes = Column(Text, nullable=True)


class Dataset(Base):
    __tablename__ = "datasets"
    __table_args__ = (
        CheckConstraint(
            "evidence_type IN ('observed', 'derived', 'simulated', 'reanalysis', 'modelled')",
            name="ck_datasets_evidence_type",
        ),
        CheckConstraint(
            "coverage_start IS NULL OR coverage_end IS NULL OR coverage_start <= coverage_end",
            name="ck_datasets_coverage_order",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    dataset_code = Column(String(96), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    provider = Column(String(160), nullable=False)
    evidence_type = Column(String(64), nullable=False, index=True)
    redistribution_status = Column(String(64), nullable=False)
    coverage_start = Column(DateTime, nullable=True)
    coverage_end = Column(DateTime, nullable=True)
    source_reference = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (
        Index("ix_observation_station_variable_time", "station_id", "variable_id", "observed_at"),
        Index("ix_observation_source_time", "source_id", "observed_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(Integer, ForeignKey("stations.id"), nullable=False, index=True)
    variable_id = Column(Integer, ForeignKey("variables.id"), nullable=False, index=True)
    source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=False, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=True, index=True)
    observed_at = Column(DateTime, nullable=False, index=True)
    value = Column(Float, nullable=False)
    quality_flag = Column(String(64), nullable=True)
    signal_status = Column(String(32), nullable=True)
    ingested_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)


class Threshold(Base):
    __tablename__ = "thresholds"
    __table_args__ = (
        CheckConstraint(
            "threshold_type IN ('official_operational', 'research_statistical', 'prototype_demo')",
            name="ck_thresholds_type",
        ),
        CheckConstraint(
            "valid_from IS NULL OR valid_to IS NULL OR valid_from <= valid_to",
            name="ck_thresholds_validity_order",
        ),
        Index("ix_threshold_station_variable_active", "station_id", "variable_id", "active"),
        Index("ix_threshold_station_variable_type_validity", "station_id", "variable_id", "threshold_type", "valid_from", "valid_to"),
    )

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(Integer, ForeignKey("stations.id"), nullable=False, index=True)
    variable_id = Column(Integer, ForeignKey("variables.id"), nullable=False, index=True)
    threshold_type = Column(String(32), nullable=False, index=True)
    value = Column(Float, nullable=False)
    # Unit is defined by Variable. Repeating it here would allow the threshold
    # and variable to disagree and would weaken the normalized design.
    source_reference = Column(Text, nullable=True)
    valid_from = Column(DateTime, nullable=True)
    valid_to = Column(DateTime, nullable=True)
    active = Column(Boolean, nullable=False, default=True, index=True)


# ==============================================================================
# 1. DATABASE MODEL (SQLAlchemy)
# Think of this as the architectural drawing for our database table.
# ==============================================================================

class TelemetryRecord(Base):
    # __tablename__ is required. It tells SQLite exactly what to name this table.
    __tablename__ = "telemetry"

    # Now we define the columns (the vertical pillars) of our table.
    
    # 'id' is our primary key. This means every piece of data gets a unique tracking number (1, 2, 3...).
    # 'index=True' acts like an index in a book; it makes the database much faster when searching for a specific ID.
    id = Column(Integer, primary_key=True, index=True)
    
    # We create columns that perfectly match the data being sent by our flood_sensor_simulator.py.
    # We index 'station_id' because we will frequently want to ask: "Show me all data for Station 1".
    station_id = Column(String(64), index=True)
    station_name = Column(String(160))
    # Provenance makes dual-source data auditable: dashboard users can tell
    # apart a reproducible simulator reading and a physical sensor reading.
    data_source = Column(String(24), nullable=False, server_default="simulated", index=True)
    
    lat = Column(Float)
    lon = Column(Float)
    
    # We store the exact time the reading was taken.
    timestamp = Column(DateTime)
    
    # Core sensor metrics (using Float because they will have decimals, e.g., 2.14 meters).
    water_level_m = Column(Float)
    danger_level_m = Column(Float)
    # Every legacy threshold is explicitly typed; existing rows migrate as demo.
    threshold_type = Column(String(32), nullable=False, server_default="prototype_demo")
    rainfall_mm_hr = Column(Float)
    flow_rate_m3s = Column(Float)
    battery_pct = Column(Float)
    
    # Text string showing if the sensor is "online" or "degraded"
    signal = Column(String(32))


# ==============================================================================
# 2. PYDANTIC MODELS (Data Validation & Serialization)
# These classes do NOT talk to the database. They act as "Security Guards" at the door of our API.
# If a sensor tries to send us the word "hello" instead of a number for the water level,
# these Pydantic models will instantly reject the request and return a helpful error.
# ==============================================================================

# This class defines the exact payload we expect to RECEIVE from the sensors (via a POST request).
class TelemetryCreate(BaseModel):
    # Both CSV and REST must reject non-finite sensor values before arithmetic.
    model_config = {"allow_inf_nan": False, "str_strip_whitespace": True}
    station_id: str = Field(min_length=1, max_length=64)
    station_name: str = Field(min_length=1, max_length=160)
    # Existing simulator clients can omit this field; an ESP32 must explicitly
    # send ``hardware`` when it posts a real measurement.
    data_source: Literal["simulated", "hardware"] = "simulated"
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    timestamp: datetime # Pydantic is smart enough to ensure they send a valid date/time format.
    water_level_m: float = Field(ge=0)
    danger_level_m: float = Field(gt=0)
    threshold_type: Literal["official_operational", "research_statistical", "prototype_demo"] = "prototype_demo"
    # Optional fields distinguish "not measured" from a genuine zero.
    rainfall_mm_hr: float | None = Field(default=None, ge=0)
    flow_rate_m3s: float | None = Field(default=None, ge=0)
    battery_pct: float | None = Field(default=None, ge=0, le=100)
    signal: str = Field(min_length=1, max_length=32)

# This class defines the data we SEND BACK out to our Dashboard (via a GET request).
# Notice that it inherits `(TelemetryCreate)`. This means it automatically gets all the fields above (station_id, lat, etc).
# But we ADD the 'id' field. Why? Because when data comes in from the sensor, it doesn't have an ID yet.
# It only gets an ID *after* it is saved in the database. 
class TelemetryResponse(TelemetryCreate):
    id: int

    # API responses may be built from SQLAlchemy rows or normalized projection
    # objects. Pydantic v2 reads either through attribute access.
    model_config = ConfigDict(from_attributes=True)


# This schema is deliberately separate from the stored telemetry schema.  It
# represents a calculated, current status for the dashboard, keeping raw sensor
# evidence distinct from an explainable decision-support recommendation.
class RiskStatus(BaseModel):
    station_id: str
    station_name: str
    data_source: Literal["simulated", "hardware"]
    lat: float
    lon: float
    timestamp: datetime
    water_level_m: float
    danger_level_m: float
    threshold_type: Literal["official_operational", "research_statistical", "prototype_demo"]
    rainfall_mm_hr: float | None
    flow_rate_m3s: float | None
    rate_of_rise_m: float = Field(description="Water-level change in metres since the previous reading for the same station.")
    battery_pct: float | None
    signal: str
    risk_level: str
    risk_ratio: float
    ml_probability: float | None = None
    model_available: bool
    message: str
    color: str = Field(description="Hex colour used as a secondary, never sole, risk indicator.")
    language: Literal["en", "ha", "fr", "ig", "yo"] = "en"
    alert_channels: dict[str, str]


class UserRegister(BaseModel):
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=6, max_length=160, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone_number: str = Field(min_length=7, max_length=32, pattern=r"^\+?[0-9][0-9\s\-()]{6,31}$")
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: str = Field(min_length=6, max_length=160)
    password: str = Field(min_length=1, max_length=128)


class UserPublic(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    phone_number: str | None = None
    role: str = "user"
    preferred_language: str = "en"
    email_updates: bool = True
    sms_updates: bool = True
    whatsapp_updates: bool = False

    model_config = ConfigDict(from_attributes=True)


class AuthResponse(BaseModel):
    message: str
    user: UserPublic
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class RoleUpdate(BaseModel):
    """Admin-only request body for changing a user's operational role."""

    role: Literal["viewer", "operator", "admin"]


class AlertActionRequest(BaseModel):
    """Operator notes supplied when an alert changes workflow state."""

    notes: str = Field(default="", max_length=1000)


class AlertEventPublic(BaseModel):
    """API-safe alert event returned to the dashboard and operator tools."""

    id: int
    station_id: str
    station_name: str
    data_source: str
    risk_level: str
    message: str
    channels: dict[str, str]
    status: Literal["new", "acknowledged", "escalated", "resolved"]
    operator_notes: str | None = None
    created_at: datetime
    updated_at: datetime
    acknowledged_by: int | None = None
    acknowledged_at: datetime | None = None
    escalated_by: int | None = None
    escalated_at: datetime | None = None
    resolved_by: int | None = None
    resolved_at: datetime | None = None


class AlertAuditPublic(BaseModel):
    """API-safe audit entry for one alert workflow change."""

    id: int
    alert_id: int
    action: str
    from_status: str | None = None
    to_status: str
    notes: str | None = None
    operator_id: int
    operator_email: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ScenarioRunPublic(BaseModel):
    """Summary of an operator-triggered scenario run."""

    id: int
    station_id: str
    station_name: str
    scenario: str
    before_risk: str
    after_risk: str
    before_water_level_m: float
    after_water_level_m: float
    operator_id: int
    operator_email: str
    metrics_snapshot: dict
    created_at: datetime


class CsvUploadResult(BaseModel):
    """Summary returned after operator CSV telemetry upload."""

    accepted: int
    rejected: int
    errors: list[str]


class ModelEvaluationResponse(BaseModel):
    """Model metrics shaped for the evaluation dashboard."""

    data_source: str
    prediction_target: str
    prediction_horizon_ticks: int
    baseline_warning_ratio: float
    label_policy: dict
    results: dict
    feature_importances: dict
    generated_at: datetime | None = None
    retrieved_at: datetime
    train_samples: int | None = None
    test_samples: int | None = None


class NewsArticle(BaseModel):
    """Normalized news/resource item from configured external feeds."""

    title: str
    source: str
    url: str
    published_at: datetime | None = None
    description: str | None = None
    provider: str


class NewsFeedResponse(BaseModel):
    """News-feed response that stays honest when providers are not configured."""

    configured: bool
    provider: str
    query: str
    articles: list[NewsArticle]
    message: str
    fetched_at: datetime


class HealthStatus(BaseModel):
    """Small health-check response for Docker and CI smoke tests."""

    status: Literal["ok", "degraded"]
    database: str
    model_available: bool
    news_provider: str
    timestamp: datetime
