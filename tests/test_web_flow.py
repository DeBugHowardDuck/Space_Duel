import pytest
from flask.testing import FlaskClient

try:
    from app import create_app  # type: ignore

    _app = create_app()
except Exception:
    from app import app as _app  # type: ignore


@pytest.fixture()
def client() -> FlaskClient:
    _app.config.update(TESTING=True, SECRET_KEY="test")
    with _app.test_client() as c:
        yield c


def _get_csrf(client: FlaskClient) -> str:
    client.get("/fight")
    with client.session_transaction() as s:
        token = s.get("_csrf_token")
    return str(token or "")


def test_csrf_required(client: FlaskClient) -> None:
    r = client.post("/fight/hit")
    assert r.status_code == 400  # без токена — 400


def test_htmx_partial(client: FlaskClient) -> None:
    r = client.get("/fight", headers={"HX-Request": "true"})
    assert r.status_code == 200
    body = r.data.lower()
    assert b"<html" not in body
    assert b'id="fight-panel"' in body


def test_auto_ai_until_player_turn(client: FlaskClient) -> None:
    token = _get_csrf(client)
    r = client.post(
        "/fight/hit",
        headers={"X-CSRF-Token": token, "HX-Request": "true"},
    )
    assert r.status_code == 200
    html = r.data.decode("utf-8")
    assert ("Ваш ход" in html) or ("chip-you" in html)


def test_end_banner(client: FlaskClient) -> None:
    token = _get_csrf(client)
    html = ""
    for _ in range(30):
        r = client.post(
            "/fight/hit",
            headers={"X-CSRF-Token": token, "HX-Request": "true"},
        )
        assert r.status_code == 200
        html = r.data.decode("utf-8")
        if any(x in html for x in ("Победа", "Поражение", "Ничья")):
            break
    assert any(x in html for x in ("Победа", "Поражение", "Ничья"))
