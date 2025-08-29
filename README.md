# wien_api

![Build](https://img.shields.io/github/actions/workflow/status/${REPO_SLUG}/docker-publish.yml?branch=${DEFAULT_BRANCH})
![Docker Pulls](https://img.shields.io/docker/pulls/${IMAGE_DH_SLUG})
![Image Size](https://img.shields.io/docker/image-size/${IMAGE_DH_SLUG}/${IMAGE_DH_REPO}/${IMAGE_DH_NAME}/${TAG_DISPLAY}?label=size%20(${TAG_DISPLAY}))

A lightweight service that consumes the **Wiener Linien Realtime API** and republishes
departures over **MQTT**, provides a **REST/SSE API**, a minimal **web UI**, and integrates with **Home Assistant** via MQTT Discovery.

---

## Supported tags

- `${TAG_DISPLAY}` (multi-arch: `linux/amd64`, `linux/arm64`, `linux/arm/v7`)
- Semantic tags on releases (e.g. `1.2.3`, `1.2`, `1`) when pushing `v1.2.3`

Images:
- Docker Hub: `docker.io/${IMAGE_DH}:${TAG_DISPLAY}`
- GHCR: `ghcr.io/${GHCR_OWNER}/${IMAGE_NAME}:${TAG_DISPLAY}`

---

## Quick start

```bash
docker run -d --name wien_api \
  -p 5000:5000 \
  -e MOSQUITTO_HOST=mosquitto \
  -e MOSQUITTO_USER=mqtt \
  -e MOSQUITTO_PASS=secret \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  ${IMAGE_DH}:${TAG_DISPLAY}
```

## Configuration

All settings are provided via config.yaml (YAML with ${ENV[:default]} interpolation).

Key sections:

- `mqtt.*` (broker, base_topic, retain, discovery)
- `http.*` (bind/port)
- `wien.*` (interval, diva_ids/stop_ids)
- `boards.*` (curated views, max_departures, regex on towards)

Example: see the *config.yaml.example* in the GitHub repository.

## HTTP API

- `GET /health` → service status
- `GET /api/wien` → snapshot of cached departures
- `GET /api/board/<id>` → curated board (departures trimmed server-side)
- `GET /api/stream` → SSE (snapshot + updates)
- `POST /api/ha/announce` → re-publish MQTT Discovery

## MQTT Topics

- Departures (JSON): `${BASE_TOPIC}/<ident>`
- Availability (retained): `${BASE_TOPIC}/availability`
- Home Assistant:
  - Discovery (retained): `${DISCOVERY_PREFIX}/sensor/<sensor_id>/config`
  - State: `${BASE_TOPIC}/boards/<sensor_id>/state`
  - Attributes: `${BASE_TOPIC}/boards/<sensor_id>/attributes`

## Home Assistant

With discovery enabled in config.yaml the sensors appear automatically.
Re-announce discovery after a HA restart:

```bash
curl -X POST http://<host>:5000/api/ha/announce
```

## License

MIT. Not affiliated with Wiener Linien. Respect API fair use (≥ 15s interval).
