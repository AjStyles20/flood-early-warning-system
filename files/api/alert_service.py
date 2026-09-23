"""Alert workflow application service.

This module owns persistent alert lifecycle rules.  HTTP routes remain
responsible for authentication/transport concerns; this service owns duplicate
suppression, safe bulletin wording, workflow transitions, and audit persistence.

Alert records are decision-support workflow records.  They do not represent
autonomous emergency orders or proof that SMS/email messages were delivered.
"""

import json
from datetime import datetime
from typing import Literal

from sqlalchemy.orm import Session

import models


ACTIVE_STATUSES = ("new", "acknowledged", "escalated")
ALERT_WORTHY_LEVELS = {"Moderate", "High", "Severe"}
CORE_CHANNELS = {"web": "available", "email": "simulated", "sms": "simulated"}

_ALLOWED_TRANSITIONS = {
    "new": {"acknowledged", "escalated", "resolved"},
    "acknowledged": {"escalated", "resolved"},
    "escalated": {"resolved"},
    "resolved": set(),
}


class AlertNotFoundError(LookupError):
    """Raised when an alert workflow operation targets an unknown event."""


class InvalidAlertTransitionError(ValueError):
    """Raised when an operator requests an invalid workflow transition."""


def channels() -> dict[str, str]:
    """Return a copy of the approved core-channel capability state."""
    return dict(CORE_CHANNELS)


def to_public(alert: models.AlertEvent) -> dict:
    """Serialize one persistent alert event for API/dashboard clients."""
    try:
        parsed_channels = json.loads(alert.channels_json or "{}")
    except json.JSONDecodeError:
        parsed_channels = {}
    return {
        "id": alert.id,
        "station_id": alert.station_id,
        "station_name": alert.station_name,
        "data_source": alert.data_source,
        "risk_level": alert.risk_level,
        "message": alert.message,
        "channels": parsed_channels,
        "status": alert.status,
        "operator_notes": alert.operator_notes,
        "created_at": alert.created_at,
        "updated_at": alert.updated_at,
        "acknowledged_by": alert.acknowledged_by,
        "acknowledged_at": alert.acknowledged_at,
        "escalated_by": alert.escalated_by,
        "escalated_at": alert.escalated_at,
        "resolved_by": alert.resolved_by,
        "resolved_at": alert.resolved_at,
    }


def record_audit(
    db: Session,
    alert: models.AlertEvent,
    operator: models.User,
    action: str,
    from_status: str | None,
    to_status: str,
    notes: str,
) -> None:
    """Stage an immutable operator-workflow audit row in the current transaction."""
    db.add(
        models.AlertAuditLog(
            alert_id=alert.id,
            action=action,
            from_status=from_status,
            to_status=to_status,
            notes=notes.strip()[:1000] or None,
            operator_id=operator.id,
            operator_email=operator.email,
        )
    )


def persist_event(
    db: Session,
    station_id: str,
    station_name: str,
    data_source: str,
    risk_level: str,
    message: str,
) -> models.AlertEvent | None:
    """Create/update one active alert; suppress duplicate active workflow tasks."""
    if risk_level not in ALERT_WORTHY_LEVELS:
        return None

    active_alert = (
        db.query(models.AlertEvent)
        .filter(
            models.AlertEvent.station_id == station_id,
            models.AlertEvent.data_source == data_source,
            models.AlertEvent.status.in_(ACTIVE_STATUSES),
        )
        .order_by(models.AlertEvent.updated_at.desc(), models.AlertEvent.id.desc())
        .first()
    )
    now = datetime.utcnow()
    safe_message = message if message.endswith("follow official guidance.") else f"{message} follow official guidance."

    if active_alert:
        active_alert.station_name = station_name
        active_alert.risk_level = risk_level
        active_alert.message = safe_message
        active_alert.channels_json = json.dumps(channels())
        active_alert.updated_at = now
        db.commit()
        db.refresh(active_alert)
        return active_alert

    alert = models.AlertEvent(
        station_id=station_id,
        station_name=station_name,
        data_source=data_source,
        risk_level=risk_level,
        message=safe_message,
        channels_json=json.dumps(channels()),
        status="new",
        created_at=now,
        updated_at=now,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def change_status(
    db: Session,
    alert_id: int,
    target_status: Literal["acknowledged", "escalated", "resolved"],
    action: str,
    notes: str,
    operator: models.User,
) -> dict:
    """Apply a valid operator transition and write its audit event atomically."""
    alert = db.get(models.AlertEvent, alert_id)
    if alert is None:
        raise AlertNotFoundError(alert_id)
    if target_status not in _ALLOWED_TRANSITIONS.get(alert.status, set()):
        raise InvalidAlertTransitionError(f"{alert.status} -> {target_status}")

    previous_status = alert.status
    now = datetime.utcnow()
    alert.status = target_status
    alert.updated_at = now
    alert.operator_notes = notes.strip()[:1000] or alert.operator_notes

    if target_status == "acknowledged":
        alert.acknowledged_by = operator.id
        alert.acknowledged_at = now
    elif target_status == "escalated":
        if not alert.acknowledged_at:
            alert.acknowledged_by = operator.id
            alert.acknowledged_at = now
        alert.escalated_by = operator.id
        alert.escalated_at = now
    else:
        alert.resolved_by = operator.id
        alert.resolved_at = now

    record_audit(db, alert, operator, action, previous_status, target_status, notes)
    db.commit()
    db.refresh(alert)
    return to_public(alert)


def audit_trail(db: Session, alert_id: int) -> list[models.AlertAuditLog]:
    """Return the ordered audit history for an existing alert."""
    if db.get(models.AlertEvent, alert_id) is None:
        raise AlertNotFoundError(alert_id)
    return (
        db.query(models.AlertAuditLog)
        .filter(models.AlertAuditLog.alert_id == alert_id)
        .order_by(models.AlertAuditLog.created_at.asc(), models.AlertAuditLog.id.asc())
        .all()
    )
