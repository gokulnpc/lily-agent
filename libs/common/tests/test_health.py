from fastapi import FastAPI
from fastapi.testclient import TestClient

from lily_common.health import router


def make_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_healthz() -> None:
    response = make_client().get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz() -> None:
    response = make_client().get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
