import asyncio
from app.automation import PaperAutomation
from app.paper import PaperBroker


def test_automation_starts_and_stops(tmp_path):
    broker = PaperBroker(str(tmp_path / "paper.db"))
    def fake_analyzer(symbol, market, equity):
        return {"instrument": {"quote_currency": "USD"},
                "proposal": {"action": "WAIT", "entry": 100},
                "risk_approved_paper_order": None}
    service = PaperAutomation(broker, fake_analyzer)
    async def exercise():
        started = await service.start([{"symbol": "BTC-USD", "market": "crypto"}], 60)
        assert started["running"] is True
        await asyncio.sleep(0.01)
        stopped = await service.stop()
        assert stopped["running"] is False
        assert stopped["execution_mode"] == "paper_only"
    asyncio.run(exercise())


def test_automation_refuses_invalid_scan_interval(tmp_path):
    import pytest
    broker = PaperBroker(str(tmp_path / "paper.db"))
    service = PaperAutomation(broker, lambda *args: {})
    async def exercise():
        with pytest.raises(ValueError):
            await service.start([{"symbol": "RELIANCE", "market": "stocks"}], 5)
    asyncio.run(exercise())
