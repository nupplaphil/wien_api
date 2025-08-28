# entrypoint.py
from wien_api.config import load_config
from wien_api import create_app
from wien_api.mqtt_worker import start_background
from waitress import serve

def main():
    cfg = load_config("/app/config.yaml")
    app = create_app(cfg)
    start_background(cfg)
    serve(app, listen=f"{cfg.http.bind}:{cfg.http.port}", threads=cfg.http.waitress_threads)

if __name__ == "__main__":
    main()

