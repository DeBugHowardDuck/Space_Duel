from __future__ import annotations

from flask import Blueprint, jsonify
from flask.typing import ResponseReturnValue

bp = Blueprint("health", __name__)


@bp.get("/healthz")
def healthz() -> ResponseReturnValue:
    return jsonify({"status": "ok"}), 200


@bp.get("/readyz")
def readyz() -> ResponseReturnValue:
    return jsonify({"status": "ok"}), 200
