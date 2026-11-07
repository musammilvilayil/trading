import pytest
from app.paper import PaperBroker, PaperTradeRejected


def test_paper_broker_persists_and_marks_to_market(tmp_path):
    path = str(tmp_path / "paper.db")
    broker = PaperBroker(path)
    order = broker.place_order("BTC-USD", "crypto", "buy", 0.01, 1000, 990)
    assert order["status"] == "filled_simulated"
    assert PaperBroker(path).portfolio()["positions"][0]["quantity"] == 0.01


def test_paper_broker_rejects_excessive_trade_risk(tmp_path):
    broker = PaperBroker(str(tmp_path / "paper.db"))
    with pytest.raises(PaperTradeRejected, match="0.5%"):
        broker.place_order("BTC-USD", "crypto", "buy", 20, 100, 90)


def test_paper_broker_sell_calculates_realized_pnl(tmp_path):
    broker = PaperBroker(str(tmp_path / "paper.db"))
    broker.place_order("BTC-USD", "crypto", "buy", 0.01, 1000, 990)
    sell = broker.place_order("BTC-USD", "crypto", "sell", 0.01, 1100)
    assert sell["realized_pnl"] > 0
    assert broker.portfolio()["positions"] == []


def test_paper_broker_stop_loss_triggers_exit(tmp_path):
    broker = PaperBroker(str(tmp_path / "paper.db"))
    broker.place_order("BTC-USD", "crypto", "buy", 0.01, 1000, 990)
    result = broker.process_price("BTC-USD", "crypto", 980)
    assert result["stop_triggered"] is True
    assert result["order"]["side"] == "sell"
