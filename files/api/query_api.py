"""Read-only helper for checking a running FloodWatch API from PowerShell.

Monitoring reads require a registered account. This helper accepts an existing
session bearer token locally; it never creates an account, changes a role or
prints the token. Public news and general advice do not need this helper.
"""

import argparse
import getpass
import json
import os
import urllib.parse
import urllib.request
from typing import Any


API_ROOT = os.getenv("FLOODWATCH_API_ROOT", "http://127.0.0.1:8000").rstrip("/")


def request_json(path: str, bearer_token: str) -> Any:
    """Use the same server-validated session as an authenticated API client."""
    request = urllib.request.Request(f"{API_ROOT}{path}", method="GET")
    request.add_header("Accept", "application/json")
    request.add_header("Authorization", f"Bearer {bearer_token}")
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read())


def risk_path(data_source: str) -> str:
    """Build a safe risk-status URL for simulated, hardware, or hybrid mode."""
    query = urllib.parse.urlencode({"data_source": data_source})
    return f"/api/risk-status?{query}"


def print_telemetry(bearer_token: str) -> None:
    """Print stored telemetry rows in a compact defense-friendly format."""
    readings = request_json("/api/telemetry", bearer_token)
    print(f"Telemetry records: {len(readings)}")
    print("-" * 72)
    for reading in readings:
        status = "FLOOD RISK" if reading["water_level_m"] >= reading["danger_level_m"] else "normal"
        print(
            f"[{reading['id']:>3}] {reading['station_id']} | {reading['data_source']:<9} | "
            f"{reading['station_name']} | {reading['water_level_m']}m / "
            f"danger {reading['danger_level_m']}m -> {status}"
        )
    print("-" * 72)


def print_risk_status(data_source: str, bearer_token: str) -> None:
    """Print newest station risk status for the selected source mode."""
    statuses = request_json(risk_path(data_source), bearer_token)
    print(f"Risk-status rows ({data_source}): {len(statuses)}")
    print("-" * 72)
    for station in statuses:
        ml_probability = station["ml_probability"]
        probability_text = "n/a" if ml_probability is None else f"{ml_probability:.3f}"
        print(
            f"{station['station_id']} | {station['data_source']:<9} | "
            f"{station['risk_level']:<8} | ratio {station['risk_ratio']:<6} | "
            f"ML {probability_text:<5} | {station['station_name']}"
        )
        print(f"  {station['message']}")
    print("-" * 72)


def main() -> None:
    """Prompt privately for a session token before querying protected reads."""
    parser = argparse.ArgumentParser(description="Read FloodWatch telemetry/risk data from a running API.")
    parser.add_argument(
        "--view",
        choices=["telemetry", "risk", "all"],
        default="all",
        help="which API output to print",
    )
    parser.add_argument(
        "--source",
        choices=["simulated", "hardware", "hybrid"],
        default="hybrid",
        help="risk-status source mode",
    )
    args = parser.parse_args()

    # An existing bearer token comes from /api/auth/login. Avoid a --token
    # option because command arguments can be retained in shell history.
    # getpass hides interactive input; the environment option also supports
    # local automation without hardcoding credentials in this source file.
    bearer_token = os.getenv("FLOODWATCH_API_TOKEN", "").strip()
    if not bearer_token:
        bearer_token = getpass.getpass("Registered-account bearer token (hidden): ").strip()
    if not bearer_token:
        parser.error("A registered-account bearer token is required.")

    if args.view in {"telemetry", "all"}:
        print_telemetry(bearer_token)
    if args.view in {"risk", "all"}:
        print_risk_status(args.source, bearer_token)


if __name__ == "__main__":
    main()
