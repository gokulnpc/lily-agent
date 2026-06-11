from fastapi.testclient import TestClient

from gateway import __version__
from gateway.main import create_app


def test_root_reports_service_and_version() -> None:
    client = TestClient(create_app())
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"service": "gateway", "version": __version__}


def test_health_endpoints_mounted() -> None:
    client = TestClient(create_app())
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 200
