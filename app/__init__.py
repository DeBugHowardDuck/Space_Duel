from __future__ import annotations

from pathlib import Path  # ← ДОБАВИЛИ

from dotenv import load_dotenv
from flask import Flask

from app.config import make_config_from_env
from app.web import bp as web_bp


def create_app() -> Flask:
    """
    Фабрика Flask-приложения.
    """
    load_dotenv()

    # База путей
    pkg_dir: Path = Path(__file__).resolve().parent  # .../app
    project_root: Path = pkg_dir.parent  # корень репозитория

    app = Flask(
        __name__,
        template_folder=str(project_root / "templates"),  # ← ВАЖНО: корень/templates
        static_folder=str(project_root / "static"),  # ← ВАЖНО: корень/static
    )

    cfg = make_config_from_env()
    app.config.from_object(cfg)

    app.register_blueprint(web_bp)
    return app


__all__: list[str] = []
