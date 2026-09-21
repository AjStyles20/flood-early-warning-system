#!/usr/bin/env python3
"""
Simulated Multi-Station IoT Flood Sensor Network
==================================================

Generates controlled synthetic telemetry for software integration, dashboard,
alert-workflow and scenario testing. It is not a hydrological model and its
outputs are not observational evidence of Lokoja or any named Nigerian gauge.

If no MQTT broker is reachable, it automatically falls back to writing
each reading to a local JSONL log (data/simulated_telemetry.jsonl) and
printing it to the console, so the simulator is runnable and testable
with zero external setup.

Usage
-----
    python3 flood_sensor_simulator.py --mode normal
    python3 flood_sensor_simulator.py --mode flood --stations 5 --interval 2
    python3 flood_sensor_simulator.py --mode flood --broker YOUR_BROKER_HOST --port 1883

Modes
-----
normal : water levels fluctuate mildly around each station's baseline
flood  : water levels ramp upward over the run to simulate a rising-flood
         event, useful for testing the prediction model and the
         decision-support "Moderate / High / Severe" thresholds with
         guidance to follow official guidance.
"""

import argparse
import json
import math
import os
import random
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False

# ---------------------------------------------------------------------------
# Station definitions
#
# Coordinates are illustrative points along/near the Niger and Benue river
# corridors and a Lagos-area drainage point, matching the national-level
# scope described in the Research Foundation and Novelty Statement
# (Section 6: Nigerian Context). Replace with real gauge locations once
# a specific deployment area is confirmed.
# ---------------------------------------------------------------------------
DEFAULT_STATIONS = [
    {"station_id": "NG-LOK-01", "name": "Lokoja Confluence Gauge",       "lat": 7.7999, "lon": 6.7333, "baseline_m": 3.50, "danger_m": 10.00},
    {"station_id": "NG-MKD-02", "name": "Makurdi Benue Bridge",         "lat": 7.7333, "lon": 8.5333, "baseline_m": 2.50, "danger_m": 8.00},
    {"station_id": "NG-MDG-03", "name": "Alau Dam Headwater",           "lat": 11.8333, "lon": 13.1500, "baseline_m": 2.00, "danger_m": 6.00},
    {"station_id": "NG-YEN-04", "name": "Yenagoa Tidal Station",         "lat": 4.9267, "lon": 6.2676, "baseline_m": 1.20, "danger_m": 4.50},
    {"station_id": "NG-LOS-05", "name": "Lagos Urban Drainage Point",    "lat": 6.5244, "lon": 3.3792, "baseline_m": 0.60, "danger_m": 2.50},
    {"station_id": "NG-JBB-06", "name": "Jebba Hydro Station",          "lat": 9.1333, "lon": 4.8167, "baseline_m": 2.80, "danger_m": 7.50},
    {"station_id": "NG-KNJ-07", "name": "Kainji Reservoir Outflow",      "lat": 9.8667, "lon": 4.5667, "baseline_m": 3.00, "danger_m": 8.50},
    {"station_id": "NG-BAR-08", "name": "Baro River Port Gauge",        "lat": 8.5833, "lon": 6.4167, "baseline_m": 2.20, "danger_m": 6.50},
    {"station_id": "NG-ONT-09", "name": "Onitsha Niger Bridge",         "lat": 6.1500, "lon": 6.7833, "baseline_m": 3.00, "danger_m": 9.00},
    {"station_id": "NG-YAU-10", "name": "Yauri Upstream Reach",         "lat": 10.8167, "lon": 4.7333, "baseline_m": 1.80, "danger_m": 5.50},
    {"station_id": "NG-SOK-11", "name": "Sokoto River Gauge",           "lat": 13.0622, "lon": 5.2339, "baseline_m": 1.60, "danger_m": 5.00},
    {"station_id": "NG-YOL-12", "name": "Yola Benue Reach",             "lat": 9.2035, "lon": 12.4954, "baseline_m": 2.10, "danger_m": 6.80},
    {"station_id": "NG-JAL-13", "name": "Jalingo River Station",        "lat": 8.8937, "lon": 11.3771, "baseline_m": 1.40, "danger_m": 4.80},
    {"station_id": "NG-BNI-14", "name": "Benin Urban Drainage",         "lat": 6.3350, "lon": 5.6037, "baseline_m": 0.90, "danger_m": 3.30},
    {"station_id": "NG-PHC-15", "name": "Port Harcourt Tidal Gauge",    "lat": 4.8156, "lon": 7.0498, "baseline_m": 1.10, "danger_m": 4.10},
    {"station_id": "NG-CAL-16", "name": "Calabar Estuary Station",      "lat": 4.9757, "lon": 8.3417, "baseline_m": 1.20, "danger_m": 4.20},
    {"station_id": "NG-JOS-17", "name": "Jos Plateau Catchment",        "lat": 9.8965, "lon": 8.8583, "baseline_m": 0.80, "danger_m": 3.10},
    {"station_id": "NG-GOM-18", "name": "Gombe Gongola Gauge",          "lat": 10.2897, "lon": 11.1673, "baseline_m": 1.50, "danger_m": 5.20},
    {"station_id": "NG-GUS-19", "name": "Gusau Sokoto Tributary",       "lat": 12.1628, "lon": 6.6614, "baseline_m": 1.30, "danger_m": 4.70},
    {"station_id": "NG-KAD-20", "name": "Kaduna River Station",         "lat": 10.5105, "lon": 7.4165, "baseline_m": 1.80, "danger_m": 6.00},
]


OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
LOCAL_LOG_PATH = os.path.join(OUTPUT_DIR, "simulated_telemetry.jsonl")


def generate_reading(station, tick, total_ticks, mode):
    """Produce one simulated telemetry reading for a station at a given tick."""
    baseline = station["baseline_m"]
    danger = station["danger_m"]

    if mode == "flood":
        # Ramp water level from baseline toward (and slightly past) the
        # danger threshold over the course of the run, with noise, so the
        # controlled system receives a reproducible rising synthetic signal.
        progress = tick / max(total_ticks - 1, 1)
        ramp = (danger - baseline) * 1.15 * (progress ** 1.4)
        noise = random.uniform(-0.05, 0.05)
        water_level = round(baseline + ramp + noise, 3)
        rainfall = round(max(0.0, random.gauss(18 + 25 * progress, 6)), 2)
    else:
        # Normal mode: mild fluctuation around baseline, occasional light rain.
        water_level = round(baseline + random.uniform(-0.15, 0.20), 3)
        rainfall = round(max(0.0, random.gauss(3, 3)), 2)

    flow_rate = round(max(0.0, water_level * random.uniform(8.0, 12.0)), 2)  # m3/s, illustrative

    return {
        "station_id": station["station_id"],
        "station_name": "[SIMULATED] " + station["name"],
        # Makes simulator evidence visibly different from physical hardware.
        "data_source": "simulated",
        "lat": station["lat"],
        "lon": station["lon"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "water_level_m": water_level,
        "danger_level_m": danger,
        "threshold_type": "prototype_demo",
        "rainfall_mm_hr": rainfall,
        "flow_rate_m3s": flow_rate,
        "battery_pct": round(max(5, 100 - tick * random.uniform(0.05, 0.15)), 1),
        "signal": random.choice(["online", "online", "online", "degraded"]),  # occasional degraded link
    }


def publish_mqtt(client, topic_prefix, reading):
    topic = f"{topic_prefix}/{reading['station_id']}"
    client.publish(topic, json.dumps(reading), qos=1)


def log_local(reading):
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(LOCAL_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(reading) + "\n")
    except Exception as e:
        pass # Ignore logging errors for the sake of the API test

def post_to_api(api_url, reading, timeout_seconds):
    """Send one reading to FastAPI and report whether the API accepted it."""
    try:
        req = urllib.request.Request(api_url)
        req.add_header('Content-Type', 'application/json; charset=utf-8')
        jsondata = json.dumps(reading).encode('utf-8')
        urllib.request.urlopen(req, jsondata, timeout=timeout_seconds)
        return True
    except Exception as exc:
        print(f"[simulator] REST post failed for {reading['station_id']}: {exc}")
        return False


def try_connect_mqtt(broker, port, timeout=3):
    if not MQTT_AVAILABLE:
        return None
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    try:
        client.connect(broker, port, keepalive=timeout)
        client.loop_start()
        return client
    except Exception as exc:
        print(f"[simulator] Could not reach MQTT broker {broker}:{port} ({exc})")
        print("[simulator] Falling back to local JSONL logging only.")
        return None


def main():
    parser = argparse.ArgumentParser(description="Simulated multi-station IoT flood sensor network")
    parser.add_argument("--mode", choices=["normal", "flood"], default="normal",
                         help="normal = mild fluctuation, flood = simulated rising-flood event")
    parser.add_argument("--stations", type=int, default=len(DEFAULT_STATIONS),
                         help="number of stations to simulate (max %d, default all)" % len(DEFAULT_STATIONS))
    parser.add_argument("--interval", type=float, default=2.0, help="seconds between readings")
    parser.add_argument("--ticks", type=int, default=30, help="number of reading rounds to publish")
    parser.add_argument("--broker", type=str, default=None, help="MQTT broker hostname (optional)")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--topic-prefix", type=str, default="flood/telemetry", help="MQTT topic prefix")
    parser.add_argument("--api-url", type=str, default="http://127.0.0.1:8000/api/telemetry", help="REST API endpoint to send data to")
    parser.add_argument("--api-timeout", type=float, default=10.0, help="seconds to wait for each REST API post")
    args = parser.parse_args()

    stations = DEFAULT_STATIONS[: max(1, min(args.stations, len(DEFAULT_STATIONS)))]

    client = None
    if args.broker:
        client = try_connect_mqtt(args.broker, args.port)

    print(f"[simulator] Mode: {args.mode} | Stations: {len(stations)} | "
          f"Ticks: {args.ticks} | Interval: {args.interval}s")
    print(f"[simulator] {'Publishing to MQTT ' + args.broker if client else 'No broker connected - logging locally to ' + LOCAL_LOG_PATH}")

    for tick in range(args.ticks):
        for station in stations:
            reading = generate_reading(station, tick, args.ticks, args.mode)
            log_local(reading)
            if client:
                publish_mqtt(client, args.topic_prefix, reading)
            if args.api_url:
                post_to_api(args.api_url, reading, args.api_timeout)
            status = "FLOOD RISK" if reading["water_level_m"] >= reading["danger_level_m"] else "normal"
            print(f"  [{reading['timestamp']}] {reading['station_id']} ({reading['station_name']}): "
                  f"{reading['water_level_m']} m / danger {reading['danger_level_m']} m "
                  f"| rainfall {reading['rainfall_mm_hr']} mm/hr | {status}")
        time.sleep(args.interval)

    if client:
        client.loop_stop()
        client.disconnect()

    print(f"[simulator] Done. {args.ticks * len(stations)} readings logged to {LOCAL_LOG_PATH}")


if __name__ == "__main__":
    main()
