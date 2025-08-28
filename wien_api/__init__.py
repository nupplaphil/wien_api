# wien_api/__init__.py
import os
from flask import Flask
from .config import AppConfig
from .routes import create_blueprint
from .boards import set_boards

def create_app(cfg: AppConfig) -> Flask:
    app = Flask(__name__)
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    web_dir = os.path.join(base_dir, "web")

    set_boards(cfg.boards)                       # Boards aus config.json aktivieren
    app.register_blueprint(create_blueprint(web_dir, sse_snapshot_on_connect=True))

    app.config["CFG"] = cfg
    return app

