# wien_api — Vienna Public Transport → MQTT, Web & Home Assistant

A lightweight service that consumes the **Wiener Linien Realtime API** and republishes
departures over **MQTT**, provides a **REST/SSE API**, a minimal **web UI**, and integrates
with **Home Assistant** using MQTT Discovery.

---

## Features

- Polls [Wiener Linien Realtime API](https://www.wienerlinien.at/open-data)
- Publishes departures to MQTT (`vienna/lines/<ident>`)
- Web API & SSE (`/api/wien`, `/api/board/<id>`, `/api/stream`)
- Web frontend (`/` and `/?board=<id>`)
- Configurable **boards**: curated stop/line/direction views with `max_departures`
- Home Assistant MQTT Discovery sensors

---

## Quickstart (Docker)

```yaml
services:
  wien_api:
    image: <yourname>/wien_api:latest
    restart: unless-stopped
    volumes:
      - ./config.yaml:/app/config.yaml:ro
    environment:
      MOSQUITTO_HOST: mosquitto
      MOSQUITTO_USER: mqtt
      MOSQUITTO_PASS: secret
    ports:
      - "5000:5000"
```

Start with:

```bash
docker compose up -d
```

---

## Configuration (`config.yaml`)

All settings come from a single YAML file. `${ENV[:default]}` placeholders are interpolated.

See [`config.yaml.example`](config.yaml.example) for a full example.

---

## License

MIT. Not affiliated with Wiener Linien. Respect API fair use (≥ 15s interval).
