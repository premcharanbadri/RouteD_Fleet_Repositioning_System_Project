"""Pytest fixtures: an isolated app instance backed by a temporary database."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator

import pytest

# Point the app at a throwaway SQLite file *before* anything imports settings.
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)  # noqa: SIM115 — must outlive this block
_tmp.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"
os.environ["ANTHROPIC_API_KEY"] = ""


@pytest.fixture()
def client() -> Iterator:
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
