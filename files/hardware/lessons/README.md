# Raspberry Pi Pico Learning Path

These lessons document the hands-on sequence used to build the FloodWatch hardware prototype from first principles.

They are not generic tutorials detached from the project. Each lesson records a capability that later becomes part of the FloodWatch sensing pipeline.

## Completed lessons

| Lesson | Topic | FloodWatch relevance |
|---|---|---|
| 1 | GPIO output | local indicators and actuator control |
| 2 | Digital input | switches and digital sensor interfaces |
| 3 | ADC / analog input | reading variable sensor signals |
| 4 | IR digital sensor | thresholded sensor input and active-low logic |
| 5 | Three-state warning prototype | combining sensing with LED/buzzer outputs |
| 6 | LCD/I2C investigation | display buses, device addressing, voltage-level safety |
| 7 | Improved warning behaviour | distinct local warning patterns |
| 8 | Rate-of-rise detection | identifying rapidly increasing water level |
| 9 | Filtering and persistence | noise reduction and stable state decisions |
| 10 | Water-level calibration | translating raw ADC values into meaningful level values |

## Lesson 11 — System integration

Lesson 11 begins the transition from isolated Pico experiments to the actual FloodWatch application.

Planned stages:

- **11A:** Pico outputs filtered, calibrated, machine-readable USB serial telemetry.
- **11B:** a Python bridge on the laptop reads the Pico serial stream and POSTs the required JSON payload to the FastAPI `/api/telemetry` endpoint.
- **11C:** the FloodWatch dashboard is tested in Hardware and Hybrid modes using live Pico-driven readings.

## Important architecture rule

The Pico is not the authoritative FloodWatch risk engine.

```text
Pico:
Measure → Filter → Calibrate → Transmit

Backend:
Receive → Validate → Store → Analyse → Predict → Display → Alert
```

Local SAFE/CAUTION/DANGER exercises are retained because they teach embedded logic and provide useful physical feedback, but the application-level FloodWatch risk states remain those produced by the backend.

## Planned lesson-file convention

Detailed lesson notes can be added progressively using:

```text
lesson_01_gpio_output.md
lesson_02_digital_input.md
lesson_03_analog_input.md
lesson_04_ir_sensor.md
lesson_05_warning_states.md
lesson_06_lcd_i2c.md
lesson_07_warning_patterns.md
lesson_08_rate_of_rise.md
lesson_09_filtering_persistence.md
lesson_10_water_level_calibration.md
lesson_11_hardware_integration.md
```

The chronological engineering evidence and observed results are maintained separately in `files/docs/hardware_development_log.md`.
