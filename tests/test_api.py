"""Smoke test: cijeli tok config -> API s mock adapterom i filtriranjem značajki."""
import pytest
from fastapi.testclient import TestClient

from mojtelekom.app import create_app
from mojtelekom.config import Settings


def test_prepaid_end_to_end_with_feature_filter():
    # Isključene značajke moraju doći kao null; prepaid mora proći cijelim tokom.
    app = create_app(Settings(adapter="mock", features=["status", "prepaid"], ttl_seconds=0))
    with TestClient(app) as client:
        r = client.get("/api/numbers")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 3
        assert data[0]["prepaid"]["balance"] == 12.34
        assert data[0]["usage"] is None
        assert data[0]["invoice"] is None
        assert data[2]["status"] == "blocked"

        r = client.get("/api/numbers/0921234567")  # skraćeni dohvat
        assert r.status_code == 200
        assert r.json()["prepaid"]["balance"] == 0.87

        r = client.get("/healthz")
        assert r.json() == {"ok": True, "adapter": "mock", "features": ["status", "prepaid"]}


def test_api_key_required_when_set():
    app = create_app(Settings(adapter="mock", api_key="tajna"))
    with TestClient(app) as client:
        assert client.get("/api/numbers").status_code == 401
        assert client.get("/api/numbers", headers={"X-API-Key": "tajna"}).status_code == 200


def test_unknown_feature_rejected(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("MT_FEATURES", "nema")
    with pytest.raises(ValueError, match="Nepoznate značajke"):
        Settings.from_env()
