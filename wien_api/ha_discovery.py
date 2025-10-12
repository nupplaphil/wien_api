# wien_api/ha_discovery.py
from __future__ import annotations
import json, re, time
from typing import Any, Dict, List, Tuple
from paho.mqtt.client import Client
from .config import AppConfig
from .boards import build_board

_slug_re = re.compile(r"[^a-z0-9]+")
def slugify(s: str) -> str:
    return _slug_re.sub("_", (s or "").lower()).strip("_")

def _sensor_id(board_id: str, stop_title: str, line_name: str, towards: str) -> str:
    return f"vienna_{slugify(board_id)}_{slugify(stop_title)}_{slugify(line_name)}_{slugify(towards)}"

def _topics(cfg: AppConfig, sensor_id: str) -> Dict[str, str]:
    base = cfg.mqtt.base_topic.rstrip("/")
    return {
        "state":      f"{base}/boards/{sensor_id}/state",
        "attributes": f"{base}/boards/{sensor_id}/attributes",
        "availability": f"{base}/availability",
        "config":     f"{cfg.mqtt.discovery.prefix}/sensor/{sensor_id}/config",
    }

def _device(cfg: AppConfig) -> Dict[str, Any]:
    dev = cfg.mqtt.discovery.device if cfg.mqtt.discovery else {}
    # minimale Pflichtfelder absichern
    if "identifiers" not in dev or not dev["identifiers"]:
        dev = {**dev, "identifiers": ["vienna_lines_gateway"]}
    if "name" not in dev:
        dev = {**dev, "name": "Vienna Lines"}
    return dev

def publish_discovery_for_board(client: Client, cfg: AppConfig, board_id: str) -> List[str]:
    """Veröffentlicht Discovery-Configs für alle Linien eines Boards.
       Rückgabe: Liste sensor_ids, die angelegt/aktualisiert wurden.
    """
    sensor_ids: List[str] = []
    board = build_board(board_id)  # nutzt getrimmte departures (max_departures)
    dev = _device(cfg)

    for item in board.get("items", []):
        stop_title = (item.get("title") or "Unknown").strip()
        for ln in item.get("lines", []) or []:
            name = (ln.get("name") or "").strip()
            towards = (ln.get("towards") or "").strip()
            if not name:
                continue
            sid = _sensor_id(board_id, stop_title, name, towards or "-")
            t = _topics(cfg, sid)
            payload = {
                "name": f"{stop_title} – {name}{(' → ' + towards) if towards else ''}",
                "unique_id": sid,
                "state_topic": t["state"],
                "json_attributes_topic": t["attributes"],
                "availability": [{"topic": t["availability"]}],
                "device": dev,
                "icon": "mdi:train",
                # Damit HA die Einheit/Art besser versteht (numeric, min)
                "unit_of_measurement": "min",
                "state_class": "measurement"
            }
            client.publish(t["config"], json.dumps(payload, ensure_ascii=False), qos=0, retain=True)
            sensor_ids.append(sid)
            print(f"[mqtt][ha] discovery config published for board {board_id} (sensors={len(sensor_ids)})")
    return sensor_ids

def publish_availability(client: Client, cfg: AppConfig, online: bool) -> None:
    topic = _topics(cfg, "x")["availability"]  # nur Basis gebraucht
    client.publish(topic, "online" if online else "offline", qos=0, retain=True)

def publish_board_states(client: Client, cfg: AppConfig, board_id: str) -> None:
    """Aktualisiert alle Sensorzustände eines Boards (state + attributes)."""
    board = build_board(board_id)
    ts = int(time.time())
    for item in board.get("items", []):
        stop_title = (item.get("title") or "Unknown").strip()
        for ln in item.get("lines", []) or []:
            name = (ln.get("name") or "").strip()
            towards = (ln.get("towards") or "").strip()
            if not name:
                continue
            sid = _sensor_id(board_id, stop_title, name, towards or "-")
            t = _topics(cfg, sid)
            deps = ln.get("departures") or []
            # State = erster Countdown (oder null)
            state = None
            if deps and isinstance(deps, list):
                first = deps[0]
                cd = first.get("countdown")
                if isinstance(cd, (int, float)):
                    state = int(cd)
            # publish
            attr = {
                "stop": stop_title,
                "line": name,
                "towards": towards,
                "countdowns": [int(d.get("countdown")) for d in deps if isinstance(d.get("countdown"), (int,float))],
                "ts": ts,
                "board": board_id,
            }
            client.publish(t["state"], "null" if state is None else str(state), qos=0, retain=True)
            client.publish(t["attributes"], json.dumps(attr, ensure_ascii=False), qos=0, retain=True)

