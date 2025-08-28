# wien_api/routes.py
import json, time
from queue import Empty
from flask import Blueprint, jsonify, Response, send_from_directory, stream_with_context, current_app
from .ha_discovery import publish_discovery_for_board
import paho.mqtt.client as mqtt
from .state import LAST_DATA, HUB
from .boards import build_board

def create_blueprint(web_dir: str, sse_snapshot_on_connect: bool) -> Blueprint:
    bp = Blueprint("wien", __name__)

    @bp.get("/health")
    def health():
        return jsonify({"status": "ok"}), 200

    @bp.get("/api/wien")
    def api_wien():
        return jsonify({
            "source": "mqtt-cache",
            "count": len(LAST_DATA),
            "items": list(LAST_DATA.values())
        })

    @bp.get("/api/board/<board_id>")
    def api_board(board_id: str):
        return jsonify(build_board(board_id))

    @bp.get("/api/stream")
    def api_stream():
        @stream_with_context
        def event_stream():
            q = HUB.subscribe()
            try:
                if sse_snapshot_on_connect and LAST_DATA:
                    snap = json.dumps({
                        "type": "snapshot",
                        "ts": int(time.time()),
                        "items": list(LAST_DATA.values())
                    }, ensure_ascii=False)
                    yield f"data: {snap}\n\n"
                while True:
                    try:
                        msg = q.get(timeout=30)
                        yield f"data: {msg}\n\n"
                    except Empty:
                        yield ": ping\n\n"
            finally:
                HUB.unsubscribe(q)
        return Response(event_stream(), headers={"Cache-Control": "no-cache"},
                        mimetype="text/event-stream")

    @bp.get("/")
    def index():
        return send_from_directory(web_dir, "index.html")

    import paho.mqtt.client as mqtt
    from .ha_discovery import publish_discovery_for_board

    @bp.post("/api/ha/announce")
    def ha_announce():
        cfg = current_app.config.get("CFG")
        if not cfg or not cfg.mqtt.discovery or not cfg.mqtt.discovery.enabled:
            return jsonify({"ok": False, "error": "discovery disabled"}), 400

        c = mqtt.Client(client_id="wien_api_announce", protocol=mqtt.MQTTv5,
                        callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        if cfg.mqtt.username and cfg.mqtt.password:
            c.username_pw_set(cfg.mqtt.username, cfg.mqtt.password)
        try:
            c.connect(cfg.mqtt.host, cfg.mqtt.port, keepalive=10)
            c.loop_start()
            boards = list((cfg.boards or {}).keys())
            for board_id in boards:
                publish_discovery_for_board(c, cfg, board_id)
            return jsonify({"ok": True, "boards": boards})
        finally:
            try:
                c.loop_stop()
                c.disconnect()
            except Exception:
                pass    

    return bp

