import pytest
pytest.importorskip('fastapi')
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_exposes_paper_only_safety_state():
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["live_trading_enabled"] is False


def test_dashboard_returns_persistent_inr_account():
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["capital"] == 25000
    assert "positions" in body
    assert body["live_trading_enabled"] is False


def test_automation_status_is_paper_only():
    response = client.get("/api/automation/status")
    assert response.status_code == 200
    assert response.json()["execution_mode"] == "paper_only"


def test_dhan_feed_status_is_safe_and_does_not_expose_credentials():
    response = client.get("/api/market/dhan/status")
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "DhanHQ v2"
    assert body["live_order_execution_enabled"] is False
    assert "access_token" not in body
