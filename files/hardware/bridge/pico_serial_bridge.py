import serial
import requests

from datetime import datetime, timezone


SERIAL_PORT = "COM4"
BAUD_RATE = 115200

API_URL = "http://127.0.0.1:8010/api/telemetry"


def build_payload(station_id, water_level_m):
    return {
        "station_id": station_id,
        "station_name": "Prototype Hardware Gauge",
        "data_source": "hardware",

        "lat": 9.0579,
        "lon": 7.4951,

        "timestamp": datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z"),

        "water_level_m": water_level_m,
        "danger_level_m": 2.0,

        # Prototype placeholders.
        # These are not physically measured yet.
        "rainfall_mm_hr": 0.0,
        "flow_rate_m3s": 0.0,

        # Prototype fixed value.
        # Not yet measured from hardware.
        "battery_pct": 100.0,

        "signal": "online"
    }


print("Opening Pico serial port:", SERIAL_PORT)

with serial.Serial(
    SERIAL_PORT,
    BAUD_RATE,
    timeout=2
) as pico:

    print("Connected to Pico.")
    print("Waiting for telemetry...")

    while True:

        try:
            line = (
                pico.readline()
                .decode("utf-8", errors="ignore")
                .strip()
            )

            if not line:
                continue

            print("Pico:", line)

            if not line.startswith("HW-01,"):
                continue

            parts = line.split(",")

            if len(parts) != 3:
                print("Invalid telemetry format")
                continue

            station_id = parts[0]
            raw_adc = int(parts[1])
            water_level_m = float(parts[2])

            payload = build_payload(
                station_id,
                water_level_m
            )

            response = requests.post(
                API_URL,
                json=payload,
                timeout=5
            )

            print(
                "ADC:",
                raw_adc,
                "| Water:",
                water_level_m,
                "m",
                "| API:",
                response.status_code
            )

            if not response.ok:
                print("API response:", response.text)

        except requests.RequestException as error:
            print("API connection error:", error)

        except ValueError as error:
            print("Telemetry parse error:", error)

        except KeyboardInterrupt:
            print("\nBridge stopped.")
            break