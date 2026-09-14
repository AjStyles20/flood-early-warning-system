# Hardware Development Log

This document records the physical-prototype work carried out for FloodWatch Nigeria using a Raspberry Pi Pico. It is an engineering history, not a field-validation record.

## Scope and design decision

The Raspberry Pi Pico is the embedded controller used for the prototype. The Pico performs sensing, local filtering, calibration, and telemetry output. The FloodWatch backend remains the authoritative system for persistent storage, risk analysis, ML inference, dashboard presentation, and alert generation.

Current integration path:

```text
sensor / simulated sensor
        ↓
Raspberry Pi Pico
        ↓ USB serial
laptop Python bridge
        ↓ HTTP POST
/api/telemetry
        ↓
FastAPI → SQLite → risk engine → ML → dashboard / alerts
```

Because the Pico has no built-in Wi-Fi, the laptop is used as the network gateway during development. This avoids replacing the Pico with an ESP32 and keeps the existing backend telemetry contract unchanged.

---

## Hardware available

Core prototype components used or inspected:

- Raspberry Pi Pico (RP2040)
- 830-point breadboard
- 10k potentiometer
- green, yellow, and red LEDs
- 220 ohm, 1k, and 10k resistors
- pushbuttons
- active and passive buzzers
- IR obstacle-avoidance module
- HC-SR501 PIR sensor
- SG90 servo
- LCD1602 with I2C backpack
- jumper wires
- USB cable

Additional components available for later work include SIM800L, ESP32-DevKitC, 100 uF capacitors, soldering equipment, and a robot-car kit. The ESP32 is intentionally not being used as the FloodWatch controller.

---

## Lesson 1 — GPIO output

Objective: verify Pico GPIO output and learn LED polarity, current limiting, GPIO numbering, and ground reference.

Test circuit:

- LED output on GP15
- 220 ohm resistor in series
- common ground

Observed result: LED blinked successfully under MicroPython control.

---

## Lesson 2 — Digital input

Objective: read a pushbutton and use the Pico's internal pull-up resistor.

Configuration:

- pushbutton between GP14 and GND
- `Pin.PULL_UP`
- released state = logic 1
- pressed state = logic 0
- LED on GP15 used as the output indicator

Observed result: button input successfully controlled the LED.

---

## Lesson 3 — Analog input

Objective: read a variable analog signal with the Pico ADC.

Configuration:

- 10k potentiometer outer pins to 3.3 V and GND
- potentiometer wiper to GP26 / ADC0
- `ADC.read_u16()` used for values in the approximate range 0–65535

Observed result: rotating the potentiometer changed the ADC reading successfully.

The potentiometer later became the temporary stand-in for a water-level sensor.

---

## Lesson 4 — IR obstacle sensor

Objective: learn how a simple digital sensor module provides thresholded output.

Configuration used:

- sensor powered safely from 3.3 V during the learning test
- output connected to GP14
- LED on GP15

Observed result: module state changes could be read successfully. The module commonly behaved as active-low.

Important project decision: the IR module is not treated as a real water-level sensor. It was used only as a learning exercise for sensor input and threshold logic.

---

## Lesson 5 — Three-state warning prototype

Objective: combine one analog input with three LEDs and a buzzer.

Pin assignment:

- green LED: GP15
- yellow LED: GP14
- red LED: GP13
- active buzzer: GP12
- potentiometer: GP26 / ADC0

Initial simulated thresholds:

- SAFE: ADC < 20000
- CAUTION: 20000–44999
- DANGER: >= 45000

Observed result: the Pico correctly changed LED states and activated the buzzer according to the simulated sensor level.

These states were local prototype states only. They are not the official FloodWatch backend risk categories.

---

## LCD1602 / I2C investigation

The LCD1602 was found to have a soldered I2C backpack rather than requiring the bare parallel interface.

Pico I2C test pins:

- SDA: GP4
- SCL: GP5

An I2C scan returned:

```text
I2C devices found: [39]
Address: 0x27
```

This confirmed that the backpack responded at address `0x27`.

At 3.3 V the backpack was detectable but visible LCD text was not obtained. A power-only test using Pico VBUS / 5 V and GND produced a working display.

Engineering conclusion:

- the LCD assembly works from 5 V;
- the backpack's I2C pull-ups may also rise to 5 V when powered at 5 V;
- Pico GPIO is 3.3 V logic and should not be exposed directly to a 5 V I2C bus;
- direct 5 V-powered SDA/SCL connection was therefore postponed;
- a proper bidirectional I2C level shifter such as a BSS138-based module is the preferred future solution.

---

## Lesson 7 — Improved warning behaviour

Objective: make warning outputs communicate severity more clearly.

Behaviour:

- SAFE: green LED, silent buzzer
- CAUTION: yellow LED, intermittent buzzer
- DANGER: red LED, continuous buzzer

Observed result: severity could be communicated locally using distinct light and sound patterns.

---

## Lesson 8 — Rate-of-rise detection

Objective: detect not just current water level but whether the level is changing rapidly.

Core calculation:

```text
change = current_reading - previous_reading
```

Interpretation:

- positive change = rising
- negative change = falling
- small change = stable

A deadband was introduced because ADC values fluctuate slightly even when the potentiometer is stationary.

Observed result:

- stationary ADC noise was typically small;
- deliberate fast potentiometer movement produced large positive or negative changes;
- rapid rise could trigger early caution even before the static high-level threshold was reached.

Problem discovered: state chatter. A single rapid rise could produce CAUTION followed quickly by SAFE when movement stopped.

This led directly to filtering and persistence work.

---

## Lesson 9 — Filtering and stable decisions

Objective: reduce ADC noise and avoid rapid state oscillation.

A moving sample average was introduced using 10 ADC readings separated by short delays.

Persistence was then added so a lower-risk state had to remain present for multiple readings before de-escalation.

Observed result:

- stationary values became substantially more stable;
- SAFE → CAUTION → DANGER transitions worked;
- DANGER did not immediately clear after one lower reading;
- CAUTION similarly required repeated lower-risk readings before returning to SAFE.

This demonstrated two important embedded-system concepts:

1. sensor filtering;
2. state persistence / hysteresis-like behaviour.

---

## Lesson 10 — Meaningful water-level values

Objective: convert raw ADC values into a human-readable water-level representation.

Initial simulation:

```text
percentage = ADC / 65535 × 100
```

Observed behaviour:

- low potentiometer setting produced about 0.3–0.4%;
- high setting produced about 99.6–100%.

Initial teaching thresholds:

- 0–39.9% = SAFE
- 40–69.9% = CAUTION
- 70–100% = DANGER

These thresholds are simulation values only and are not scientifically validated flood thresholds.

A two-point calibration approach was also discussed using experimentally observed raw minimum and maximum ADC values.

For future real ultrasonic sensing, the intended conversion is:

```text
water_height = sensor_mount_height - measured_distance
water_percentage = water_height / usable_height × 100
```

---

## Sensor-selection conclusions

Current situation:

- the potentiometer is the current simulated water-level input;
- the IR obstacle sensor is not an ultrasonic sensor and is not suitable as the final water-level sensor;
- the PIR sensor is unrelated to water-level measurement;
- a real ultrasonic sensor is planned for the next physical stage.

Preferred options discussed:

- verified 3.3 V-compatible HC-SR04P;
- ordinary HC-SR04 with protected ECHO line;
- waterproof JSN-SR04T-class module for a more realistic wet/outdoor prototype.

For an ordinary HC-SR04 powered at 5 V, the ECHO line must not connect directly to a Pico GPIO. A resistor divider or proper level shifting is required.

---

## SIM800L notes

SIM800L is reserved for later SMS/GPRS work.

Important electrical constraints recorded during development:

- do not power SIM800L from the Pico 3.3 V output;
- module supply is typically around 4 V and must tolerate high current bursts;
- a suitable external power supply is required;
- bulk capacitance larger than the available 100 uF alone will likely be necessary;
- an antenna is required;
- UART logic-level compatibility must be checked before connection.

---

## Integration decision before Lesson 11

The backend already owns the official FloodWatch risk pipeline. Therefore the Pico should not become a second authoritative risk engine.

Separation of responsibility:

```text
Pico
Measure → Filter → Calibrate → Transmit

FloodWatch backend
Receive → Validate → Store → Analyse → Predict → Display → Recommend / Alert
```

The planned hardware payload continues to use the existing `/api/telemetry` contract with `data_source: "hardware"`.

Fields not yet physically measured, such as rainfall and flow, may initially use clearly documented prototype placeholders during integration testing. Such values must not be presented as real sensor measurements.

---

## Next stage

Lesson 11 is the transition from isolated embedded exercises to the actual FloodWatch system:

1. Pico outputs clean machine-readable serial telemetry.
2. A laptop Python bridge reads the Pico serial port.
3. The bridge builds the existing FloodWatch JSON payload.
4. The bridge POSTs to `/api/telemetry`.
5. The dashboard is switched to Hardware or Hybrid mode.
6. Turning the potentiometer changes a live hardware-sourced FloodWatch station.

The physical ultrasonic sensor can later replace the potentiometer without changing the backend architecture.
