# wien_api/config.py
from __future__ import annotations
import os, re
from dataclasses import dataclass
from typing import Any, Dict, List
import yaml

ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)?(?::([^}]*))?\}")

def _interpolate_env(val: Any) -> Any:
    """Ersetzt ${VAR[:default]} in Strings rekursiv; andere Typen unverändert."""
    if isinstance(val, str):
        def repl(m: re.Match) -> str:
            var = m.group(1) or ""
            default = m.group(2) or ""
            return os.getenv(var, default)
        return ENV_PATTERN.sub(repl, val)
    if isinstance(val, list):
        return [_interpolate_env(x) for x in val]
    if isinstance(val, dict):
        return {k: _interpolate_env(v) for k, v in val.items()}
    return val

def _as_bool(x: Any, default: bool = False) -> bool:
    if isinstance(x, bool): return x
    if x is None: return default
    s = str(x).strip().lower()
    return s in ("1", "true", "yes", "on")

@dataclass(frozen=True)
class MQTTDiscoveryConf:
    enabled: bool
    prefix: str
    device: Dict[str, Any]

@dataclass(frozen=True)
class MQTTConf:
    host: str
    port: int
    username: str | None
    password: str | None
    base_topic: str
    retain: bool
    log_publish: bool
    reconnect_min: int
    reconnect_max: int
    discovery: MQTTDiscoveryConf | None

@dataclass(frozen=True)
class HTTPConf:
    bind: str
    port: int
    waitress_threads: int

@dataclass(frozen=True)
class WienConf:
    base_url: str
    sender: str
    activate_info: List[str]
    interval_seconds: int
    http_timeout: int
    user_agent: str
    stop_ids: List[str]
    diva_ids: List[str]

@dataclass(frozen=True)
class AppConfig:
    mqtt: MQTTConf
    http: HTTPConf
    wien: WienConf
    boards: Dict[str, Any]

def load_config(path: str = "/app/config.yaml") -> AppConfig:
    if not os.path.isfile(path):
        # Fallback: .yml
        alt = os.path.splitext(path)[0] + ".yml"
        if os.path.isfile(alt):
            path = alt
        else:
            raise RuntimeError(f"config not found at {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        raise RuntimeError(f"error reading {path}: {e}")

    cfg = _interpolate_env(data)

    mqtt = cfg.get("mqtt", {}) or {}
    disc = (mqtt.get("discovery") or {}) if isinstance(mqtt.get("discovery"), dict) else {}
    http = cfg.get("http", {}) or {}
    wien = cfg.get("wien", {}) or {}
    boards = cfg.get("boards", {}) or {}

    disc_conf = MQTTDiscoveryConf(
        enabled=_as_bool(disc.get("enabled"), False),
        prefix=str(disc.get("prefix", "homeassistant")).rstrip("/"),
        device=dict(disc.get("device") or {
            "name": "Vienna Lines",
            "identifiers": ["vienna_lines_gateway"]
        }),
    )

    mqtt_conf = MQTTConf(
        host=mqtt.get("host", "mqtt"),
        port=int(mqtt.get("port", 1883)),
        username=(mqtt.get("username") or None) or None,
        password=(mqtt.get("password") or None) or None,
        base_topic=str(mqtt.get("base_topic", "wien/abfahrten")).rstrip("/"),
        retain=_as_bool(mqtt.get("retain"), False),
        log_publish=_as_bool(mqtt.get("log_publish"), False),
        reconnect_min=int(mqtt.get("reconnect_min", 2)),
        reconnect_max=int(mqtt.get("reconnect_max", 30)),
        discovery=disc_conf,
    )
    http_conf = HTTPConf(
        bind=str(http.get("bind", "0.0.0.0")),
        port=int(http.get("port", 5000)),
        waitress_threads=int(http.get("waitress_threads", 16)),
    )
    wien_conf = WienConf(
        base_url=str(wien.get("base_url", "http://www.wienerlinien.at/ogd_realtime/monitor")),
        sender=str(wien.get("sender", "smart-home")),
        activate_info=list(wien.get("activate_info", ["stoerunglang"])),
        interval_seconds=max(int(wien.get("interval_seconds", 30)), 15),
        http_timeout=int(wien.get("http_timeout", 10)),
        user_agent=str(wien.get("user_agent", "Mozilla/5.0")),
        stop_ids=[str(x) for x in (wien.get("stop_ids") or [])],
        diva_ids=[str(x) for x in (wien.get("diva_ids") or [])],
    )
    return AppConfig(mqtt=mqtt_conf, http=http_conf, wien=wien_conf, boards=boards)

