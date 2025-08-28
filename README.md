# wien_api — Vienna Public Transport → MQTT, Web & Home Assistant

A lightweight service that consumes the **Wiener Linien Realtime API** and republishes
departures over **MQTT**, provides a **REST/SSE API**, a minimal **web UI**, and integrates
with **Home Assistant** using MQTT Discovery.

![Docker Hub](https://img.shields.io/badge/Docker%20Hub-wien__api-blue?logo=docker)
![GHCR](https://img.shields.io/badge/GHCR-wien__api-purple?logo=github)

---

## Features

- Polls [Wiener Linien Realtime API](https://www.wienerlinien.at/open-data)
- Publishes departures to MQTT (`vienna/lines/<ident>`)
- In-memory cache, exposed via:
  - `GET /api/wien` (snapshot of all items)
  - `GET /api/board/<id>` (curated board)
  - `GET /api/stream` (SSE live updates)
  - `GET /health` (service status)
- Web frontend (`/` and `/?board=<id>`) showing departures as chips
- Configurable **boards**: curated stop/line/direction views with `max_departures`
- **Home Assistant** integration via MQTT Discovery:
  - Sensors for each board/line/direction
  - State = next departure in minutes
  - Attributes = stop, line, towards, top N countdowns

---

## Quickstart (Docker)

```yaml
services:
  wien_api:
    build: ./services/wien_api
    restart: unless-stopped
    container_name: wien_api
    volumes:
      - ./config.yaml:/app/config.yaml:ro
    environment:
      # only needed if referenced in config.yaml
      - MOSQUITTO_HOST=mosquitto
      - MOSQUITTO_USER=mqtt
      - MOSQUITTO_PASS=secret
    networks:
      - smarthome
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:5000/health"]
      interval: 10s
      timeout: 3s
      retries: 5
      start_period: 10s
```

Start with

```bash
docker compose up -d --build
```

## Configuration (`config.yaml`)

All settings come from a single YAML file. `${ENV[:default]}` placeholders are interpolated.

```yaml
mqtt:
  host: ${MOSQUITTO_HOST:mqtt}
  port: 1883
  username: ${MOSQUITTO_USER:}
  password: ${MOSQUITTO_PASS:}
  base_topic: "vienna/lines"
  retain: true
  discovery:
    enabled: true
    prefix: "homeassistant"
    device:
      name: "Vienna Lines"
      identifiers: ["vienna_lines_gateway"]

http:
  bind: "0.0.0.0"
  port: 5000

wien:
  interval_seconds: 30       # fair use: ≥ 15s
  diva_ids: ["60200607", "60200627"]

boards:
  jb:
    title: "Josef-Baumann-Gasse"
    max_departures: 3
    rules:
      - stop: "Josef-Baumann-Gasse"
        lines:
          - { name: "26", towards_regex: "Hausfeldstraße\\s*U" }
      - stop: "Josef-Baumann-Gasse"
        lines:
          - { name: "25", towards_regex: "Floridsdorf" }
          - { name: "26", towards_regex: "Strebersdorf" }

  kagran-u1:
    title: "Kagran U1 → Karlsplatz"
    max_departures: 3
    rules:
      - stop: "Kagran"
        lines:
          - { name: "U1", towards_regex: "Oberlaa|Alaudagasse" }
```

## MQTT Topics

- Departures (JSON):
  `vienna/lines/<ident>` → `{ ident, ts, ok, query, items:[ … ] }`
- Availability (retained):
  `vienna/lines/availability` → `online / offline`
- Home Assistant Discovery (retained):
  `homeassistant/sensor/<sensor_id>/config`
- HA Sensors:
  - State: `vienna/lines/boards/<sensor_id>/state` → integer minutes
  - Attributes: `vienna/lines/boards/<sensor_id>/attributes` → JSON

## Home Assistant Integration

When `mqtt.discovery.enabled: true`, entities appear automatically.

Re-announce discovery (e.g. after HA restart):
```bash
curl -X POST http://<host>:5000/api/ha/announce
```

*Example Lovelace card (Glance):*
```yaml
type: glance
title: Vienna Lines
entities:
  - entity: sensor.vienna_jb_josef_baumann_gasse_25_floridsdorf_s_u
    name: 25 → Floridsdorf
    icon: mdi:train
  - entity: sensor.vienna_jb_josef_baumann_gasse_26_hausfeldstra_e_u
    name: 26 → Hausfeldstraße U
    icon: mdi:train
  - entity: sensor.vienna_jb_josef_baumann_gasse_26_strebersdorf_edmund_hawranek_platz
    name: 26 → Strebersdorf
    icon: mdi:train
  - entity: sensor.vienna_kagran_u1_kagran_u1_oberlaa
    name: U1 → Oberlaa
    icon: mdi:subway
```
Optionally create *template sensors* that join the `countdowns` attribute into a “Top-3 departures” string.

## API Endpoints
- `GET /health` → service status
- `GET /api/wien` → snapshot of all cached departures
- `GET /api/board/<id>` → curated board (limited departures)
- `GET /api/stream` → server-sent events (snapshot + updates)
- `POST /api/ha/announce`  → force re-publish of MQTT discovery

## Development
- Python 3.11+
- Flask + Waitress
- paho-mqtt
- PyYAML
- requests

Run locally:
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python entrypoint.py
```

## Notes
- Not affiliated with Wiener Linien. Data provided “as is”.
- Respect fair use of the API (≥ 15s interval).
- Recommended: `retain: true` for MQTT → ensures immediate state delivery.
- If HA does not see entities, check broker ACLs on `homeassistant/#` or configure an additional discovery prefix.
