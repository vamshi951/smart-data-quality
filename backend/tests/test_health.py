from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_health_endpoint_returns_ok(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'health.db'}")

    with TestClient(create_app(settings=settings)) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"]


def test_validation_errors_use_the_shared_error_envelope(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'validation.db'}")
    app = create_app(settings=settings)

    @app.get("/test/{item_id}")
    def get_test_item(item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    with TestClient(app) as client:
        response = client.get("/test/not-an-integer")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["details"][0]["field"] == "path.item_id"
    assert response.headers["x-request-id"]


def test_unexpected_errors_are_redacted(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'errors.db'}")
    app = create_app(settings=settings)

    @app.get("/test/failure")
    def fail() -> None:
        raise RuntimeError("sensitive internal details")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/test/failure")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "internal_server_error",
            "message": "An unexpected server error occurred.",
            "details": [],
        }
    }
    assert "sensitive internal details" not in response.text
    assert response.headers["x-request-id"]
