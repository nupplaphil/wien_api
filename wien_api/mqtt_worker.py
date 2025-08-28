# wien_api/mqtt_worker.py
import json, os, time, threading, fcntl
import requests
import paho.mqtt.client as mqtt
from .state import LAST_DATA, HUB
from .utils import safe_topic_fragment
from .fetcher import fetch_all
from .config import AppConfig
from .ha_discovery import publish_discovery_for_board, publish_availability, publish_board_states

_started = False
_started_lock = threading.Lock()
_filelock_fp = None

def _file_lock(path: str) -> bool:
    global _filelock_fp
    if _filelock_fp is not None: return True
    try:
        _filelock_fp = open(path, "w"); fcntl.flock(_filelock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB); return True
    except OSError: return False

def _extract_ident_from_query(q: str) -> str:
    if "stopId=" in q: return q.split("stopId=")[1].split("&")[0]
    if "diva=" in q:   return "diva_" + q.split("diva=")[1].split("&")[0]
    return "unknown"

def start_background(cfg: AppConfig) -> None:
    global _started
    with _started_lock:
        if _started: print("[mqtt] already started (flag); skipping"); return
        # Lockdatei an config.json koppeln (einzig pro Prozess)
        lock_path = "/tmp/wien_mqtt.lock"
        if not _file_lock(lock_path): print("[mqtt] already started (file lock); skipping"); _started = True; return
        t = threading.Thread(target=_run, name="mqtt_worker", args=(cfg,), daemon=True)
        t.start(); _started = True; print(f"[mqtt] loop thread started (pid={os.getpid()})")

def _run(cfg: AppConfig) -> None:
    session = requests.Session()

    client = mqtt.Client(client_id="wien_api", protocol=mqtt.MQTTv5,
                         callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    if cfg.mqtt.username and cfg.mqtt.password:
        client.username_pw_set(cfg.mqtt.username, cfg.mqtt.password)
    avail_topic = f"{cfg.mqtt.base_topic.rstrip('/')}/availability"
    client.will_set(avail_topic, payload="offline", qos=0, retain=True)
    client.user_data_set({"connected_once": False})
    client.reconnect_delay_set(min_delay=cfg.mqtt.reconnect_min, max_delay=cfg.mqtt.reconnect_max)

    base = cfg.mqtt.base_topic.rstrip("/")

    def on_connect(client, userdata, flags, reason_code, properties):
        first = not userdata.get("connected_once", False); userdata["connected_once"] = True
        tag = "connect" if first else "reconnect"
        ok = getattr(reason_code, "is_success", lambda: reason_code == 0)()
        print(f"[mqtt] {tag} rc={reason_code} ok={ok}")
        client.subscribe(f"{base}/+", qos=0)

        # HA availability -> online
        publish_availability(client, cfg, True)

        # HA discovery für alle Boards (falls aktiviert)
        if cfg.mqtt.discovery and cfg.mqtt.discovery.enabled:
            for board_id in (cfg.boards or {}).keys():
                publish_discovery_for_board(client, cfg, board_id)

    def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
        publish_availability(client, cfg, False)
        print(f"[mqtt] disconnected rc={reason_code}")

    def on_message(client, userdata, msg):
        try:
            topic = msg.topic
            base_prefix = f"{base}/"
            if not topic.startswith(base_prefix):
                return

            rest = topic[len(base_prefix):]  # z.B. "diva_60200607"
            if "/" in rest:
                # z.B. boards/<...>/state -> ignorieren
                return

            payload = msg.payload.decode("utf-8", errors="ignore").strip()
            data = json.loads(payload)
            if not isinstance(data, dict):
                return

            ident = data.get("ident") or rest
            LAST_DATA[ident] = data
            HUB.publish(json.dumps({
                "type": "update", "ts": int(time.time()),
                "ident": ident, "item": data
            }, ensure_ascii=False))
        except json.JSONDecodeError:
            return
        except Exception as e:
            print(f"[mqtt] on_message error: {e}")

    client.on_connect = on_connect; client.on_disconnect = on_disconnect; client.on_message = on_message

    try:
        client.connect(cfg.mqtt.host, cfg.mqtt.port, keepalive=60)
    except Exception as e:
        print(f"[mqtt] initial connect failed: {e}")
    client.loop_start()

    while True:
        try:
            items = fetch_all(cfg.wien, session)
            for item in items:
                ident_raw = _extract_ident_from_query(item.get("query", ""))
                ident = safe_topic_fragment(ident_raw)
                topic = f"{base}/{ident}"
                obj = dict(item); obj["ident"] = ident; obj["ts"] = int(time.time())
                payload = json.dumps(obj, ensure_ascii=False)
                r = client.publish(topic, payload, qos=0, retain=cfg.mqtt.retain)
                if cfg.mqtt.log_publish:
                    print(f"[mqtt] published topic={topic} rc={r.rc} bytes={len(payload)}")
                if r.rc != mqtt.MQTT_ERR_SUCCESS:
                    print(f"[mqtt] publish rc={r.rc} topic={topic}")
                if cfg.mqtt.discovery and cfg.mqtt.discovery.enabled and cfg.boards:
                    for board_id in cfg.boards.keys():
                        try:
                            publish_board_states(client, cfg, board_id)
                            if cfg.mqtt.log_publish:
                                print(f"[mqtt][ha] publish for board {board_id}")
                        except Exception as e:
                            print(f"[mqtt][ha] state publish error for board {board_id}: {e}")
        except Exception as e:
            print(f"[mqtt] publish loop error: {e}")
        time.sleep(cfg.wien.interval_seconds)

