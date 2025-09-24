from __future__ import annotations

try:
    from app import create_app  # type: ignore[attr-defined]

    app = create_app()
except Exception:
    import os

    from flask import Flask

    from app.health import bp as health_bp
    from app.web import bp as web_bp

    app = Flask(__name__)
    app.secret_key = os.getenv("SECRET_KEY", "dev-secret")

    app.register_blueprint(web_bp)
    app.register_blueprint(health_bp)
