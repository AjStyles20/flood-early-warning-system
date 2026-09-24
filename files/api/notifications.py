"""Alert notification orchestration with optional real provider delivery."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from risk_engine import RiskAssessment
import alert_delivery


RUNTIME_DIR = Path(os.getenv("FLOOD_EWS_RUNTIME_DIR", str(Path(__file__).resolve().parent)))
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
NOTIFICATION_LOG_PATH = RUNTIME_DIR / "simulated_notifications.jsonl"


def notify(station_id: str, station_name: str, assessment: RiskAssessment, data_source: str = "simulated") -> Dict[str, str]:
    """Dispatch configured providers and log the actual attempt outcome."""
    channels = alert_delivery.capabilities()
    if not assessment.should_alert:
        return {"web": "not_required", "email": "not_required", "sms": "not_required"}

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "station_id": station_id,
        "station_name": station_name,
        "data_source": data_source,
        "risk_level": assessment.risk_level,
        "message": assessment.message,
        "channels": alert_delivery.dispatch(
            station_id, station_name, assessment.risk_level, assessment.message
        ),
    }
    try:
        with NOTIFICATION_LOG_PATH.open("a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(event) + "\n")
    except OSError:
        # A temporary read-only demo environment must not prevent a sensor
        # reading being saved. Production should still monitor this log path.
        event["channels"] = {channel: "simulation_log_unavailable" for channel in channels}
    return event["channels"]
