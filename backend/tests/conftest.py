"""Test fixtures.

Environment variables are set before importing the app so the engine and
storage point at a temporary directory instead of the real database.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TMP_DIR = Path(tempfile.mkdtemp(prefix="smart-bins-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(TMP_DIR / 'test.db').as_posix()}"
os.environ["STORAGE_DIR"] = str(TMP_DIR / "storage")
os.environ["CV_MODE"] = "heuristic"
os.environ["OFFLINE_AFTER_HOURS"] = "6"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def bin_factory(client: TestClient):
    def create(name: str = "Бак", lat: float = 42.8746, lon: float = 74.5698) -> dict:
        response = client.post(
            "/bins", json={"name": name, "lat": lat, "lon": lon, "district": "Бишкек"}
        )
        assert response.status_code == 201, response.text
        return response.json()

    return create


@pytest.fixture()
def device_factory(client: TestClient):
    def create(bin_id: int, device_type: str = "virtual") -> dict:
        response = client.post("/devices", json={"bin_id": bin_id, "type": device_type})
        assert response.status_code == 201, response.text
        return response.json()

    return create
