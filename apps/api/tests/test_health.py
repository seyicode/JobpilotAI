from unittest.mock import MagicMock, patch

import psycopg
from fastapi.testclient import TestClient

from jobpilot.main import create_app

client = TestClient(create_app())


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness():
    with patch("jobpilot.api.routes.health.psycopg.connect") as connect:
        connection = MagicMock()
        connect.return_value.__enter__.return_value = connection
        assert client.get("/ready").json() == {"status": "ok"}
        connection.execute.assert_called_once_with("SELECT 1")


def test_database_failure_does_not_disclose_credentials():
    with patch("jobpilot.api.routes.health.psycopg.connect", side_effect=psycopg.OperationalError("secret")):
        response = client.get("/ready")
        assert response.status_code == 503
        assert response.json() == {"detail": "Database unavailable"}
        assert client.get("/health").status_code == 200
