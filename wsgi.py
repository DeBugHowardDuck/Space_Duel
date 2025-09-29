from __future__ import annotations

from flask import Flask

from app import create_app

app: Flask = create_app()

__all__ = ["app"]
