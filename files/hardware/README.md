# FloodWatch Hardware Development

This directory contains the Raspberry Pi Pico hardware work for the FloodWatch Nigeria flood early warning and decision support system.

The hardware layer is intentionally separated from the backend risk engine. The Pico is responsible for measurement, filtering, calibration, and transmitting telemetry. The FastAPI backend remains responsible for storage, risk classification, ML prediction, dashboard presentation, and alerting.

## Current Architecture

```text
Potentiometer / future ultrasonic sensor
        ↓
Raspberry Pi Pico
        ↓ USB serial
Python bridge on laptop
        ↓ HTTP
POST /api/telemetry
        ↓
FloodWatch FastAPI backend
        ↓
SQLite → risk engine → ML wrapper → dashboard → alerts
```

## Current Prototype Hardware

- Raspberry Pi Pico (RP2040)
- Breadboard
- 10k potentiometer used as a simulated water-level sensor
- Green, yellow, and red LEDs
- Active buzzer
- 220 ohm resistors
- Pushbuttons
- IR obstacle sensor (used only for learning digital sensor input; not treated as a water-level sensor)
- LCD1602 with I2C backpack at address `0x27` (integration postponed pending safe 3.3 V ↔ 5 V I2C interfacing)

## Pin Reference Used So Far

| Function | Pico pin |
|---|---|
| Green LED | GP15 |
| Yellow LED | GP14 |
| Red LED | GP13 |
| Active buzzer | GP12 |
| Potentiometer / ADC input | GP26 / ADC0 |
| I2C SDA (LCD tests) | GP4 |
| I2C SCL (LCD tests) | GP5 |

## Development Rules

1. The Raspberry Pi Pico remains the embedded controller for this project.
2. The backend is the authoritative source of official FloodWatch risk states (`Low`, `Moderate`, `High`, `Severe`).
3. Local Pico LED/buzzer states are for prototype feedback and demonstrations, not the official backend risk classification.
4. Prototype calibration values are not field-validated hydrological thresholds.
5. `data_source: "hardware"` identifies provenance only and must not be treated as authentication.
6. Hardware work should continue to preserve the simulator as a fallback and comparison source.

## Directory Plan

```text
files/hardware/
├── README.md
├── lessons/
├── pico/
│   └── experiments/
└── bridge/
```

The `lessons/` directory documents the sequence of experiments that led from basic GPIO control to hardware telemetry integration. Production-style Pico code and the USB serial bridge will be added only after the corresponding lesson has been tested successfully on the physical prototype.
