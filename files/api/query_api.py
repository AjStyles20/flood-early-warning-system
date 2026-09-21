"""Read-only helper for checking a running FloodWatch API from PowerShell.

Core telemetry and current risk-status reads are intentionally public because
the public dashboard/data pages depend on them. This helper performs GET-only
requests; it never creates accounts, changes roles, writes telemetry, or sends
alerts.
"""

import argparse
import json
import os
import urllib.parse
import urllib.request
from typing import Any

API_ROOT = os.getenv("FLOODWATCH_API_ROOT", "http://127.0.0.1:8000").rstrip("/")


def request_json(path: str) -> Any:
    """Read JSON from a public monitoring endpoint."""
    request = urllib.request.Request(f"{API_ROOT}{path}", method="GET")
    request.add_header("Accept", "application/json")
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read())


def risk_path(data_source: str) -> str:
    query = urllib.parse.urlencode({"data_source": data_source})
    return f"/api/risk-status?{query}"


def print_telemetry() -> None:
    readings = request_json("/api/telemetry")
    print(f"Telemetry records: {len(readings)}")
    print("-" * 72)
    for reading in readings:
        threshold_type = reading.get("threshold_type", "unknown")
        state = "AT/ABOVE THRESHOLD" if reading["water_level_m"] >= reading["danger_level_m"] else "below threshold"
        print(
            f"[{reading['id']:>3}] {reading['station_id']} | {reading['data_source']:<9} | "
            f"{reading['station_name']} | {reading['water_level_m']}m / "
            f"configured threshold {reading['danger_level_m']}m ({threshold_type}) -> {state}"
        )
    print("-" * 72)


def print_risk_status(data_source: str) -> None:
    statuses = request_json(risk_path(data_source))
    print(f"Risk-status rows ({data_source}): {len(statuses)}")
    print("-" * 72)
    for station in statuses:
        ml_probability = station.get("ml_probability")
        probability_text = "n/a" if ml_probability is None else f"{ml_probability:.3f}"
        print(
            f"{station['station_id']} | {station['data_source']:<9} | "
            f"{station['risk_level']:<8} | ratio {station['risk_ratio']:<6} | "
            f"ML {probability_text:<5} | {station['station_name']}"
        )
        print(f"  {station['message']}")
    print("-" * 72)


def main() -> None:
    parser = argparse.ArgumentParser(description="Read FloodWatch public telemetry/risk data from a running API.")
    parser.add_argument("--view", choices=["telemetry", "risk", "all"], default="all")
    parser.add_argument("--source", choices=["simulated", "hardware", "hybrid"], default="hybrid")
    args = parser.parse_args()
    if args.view in {"telemetry", "all"}:
        print_telemetry()
    if args.view in {"risk", "all"}:
        print_risk_status(args.source)


if __name__ == "__main__":
    main()
