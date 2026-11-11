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


def test_autonomous_worker_refuses_to_start_without_fresh_dhan_quote(monkeypatch):
    from app import main

    monkeypatch.setattr(main.dhan_feed_service, "latest_tick", lambda *args: None)
    response = client.post(
        "/api/automation/start",
        json={
            "watchlist": [{"symbol": "RELIANCE", "market": "stocks"}],
            "interval_seconds": 300,
        },
    )
    assert response.status_code == 422
    assert "Dhan live feed" in response.json()["detail"]


def test_autonomous_intraday_rejects_stale_dhan_tick(monkeypatch):
    from datetime import datetime, timedelta, timezone
    from app import main

    stale = {
        "received_at": (datetime.now(timezone.utc) - timedelta(seconds=20)).isoformat()
    }
    monkeypatch.setattr(main.dhan_feed_service, "latest_tick", lambda *args: stale)
    with pytest.raises(ValueError, match="stale"):
        main.require_fresh_dhan_tick("RELIANCE", "stocks")
