# wien_api

![Build](https://img.shields.io/github/actions/workflow/status/${REPO_SLUG}/docker-publish.yml?branch=${DEFAULT_BRANCH})
![Docker Pulls](https://img.shields.io/docker/pulls/${IMAGE_DH})
![Image Size](https://img.shields.io/docker/image-size/${IMAGE_DH}:${TAG_DISPLAY}?label=size)

A lightweight service that consumes the **Wiener Linien Realtime API** and republishes
departures over **MQTT**, provides a **REST/SSE API**, a minimal **web UI**, and integrates with **Home Assistant**.

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
docker run -d --name wien_api \\
  -p 5000:5000 \\
  -e MOSQUITTO_HOST=mosquitto \\
  -e MOSQUITTO_USER=mqtt \\
  -e MOSQUITTO_PASS=secret \\
  -v $(pwd)/config.yaml:/app/config.yaml:ro \\
  ${IMAGE_DH}:${TAG_DISPLAY}
```

---

## License

MIT. Not affiliated with Wiener Linien. Respect API fair use (≥ 15s interval).
