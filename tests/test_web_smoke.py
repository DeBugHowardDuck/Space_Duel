from __future__ import annotations

from flask import Flask

from app.web import bp as web_bp

try:
    from app.health import bp as health_bp
except Exception:
    health_bp = None  # type: ignore


def make_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(web_bp)
    if health_bp is not None:
        app.register_blueprint(health_bp)  # /healthz
    return app


def test_fight_page_and_csrf_post() -> None:
    app = make_app()
    with app.test_client() as c:
        r1 = c.get("/fight")
        assert r1.status_code == 200

        # достаём токен из сессии и делаем POST /fight/hit с заголовком
        with c.session_transaction() as sess:
            token = sess.get("_csrf_token")
            assert token

        r2 = c.post("/fight/hit", headers={"X-CSRF-Token": token})
        assert r2.status_code == 200


def test_healthz() -> None:
    app = make_app()
    with app.test_client() as c:
        r = c.get("/healthz")
        assert r.status_code == 200
