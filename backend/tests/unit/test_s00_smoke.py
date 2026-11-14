"""S00 smoke tests: the app imports and /health responds."""

from fastapi.testclient import TestClient

from app.cli import main as cli_main
from app.main import create_app


def test_s00_t01_health_returns_ok() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_s00_t01_cli_help_and_unknown_command() -> None:
    assert cli_main(["--help"]) == 0
    assert cli_main(["nope"]) == 2
