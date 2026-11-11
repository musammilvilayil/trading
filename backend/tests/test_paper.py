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


def test_selling_position_is_not_blocked_by_buy_order_cap(tmp_path):
    broker = PaperBroker(str(tmp_path / "paper.db"))
    broker.place_order("ABC", "stocks", "buy", 2.4, 1000, 990)
    sell = broker.place_order("ABC", "stocks", "sell", 2.4, 1300)
    assert sell["status"] == "filled_simulated"


def test_same_symbol_can_exist_in_multiple_markets(tmp_path):
    broker = PaperBroker(str(tmp_path / "paper.db"))
    broker.place_order("ABC", "stocks", "buy", 1, 100, 99)
    broker.place_order("ABC", "crypto", "buy", 1, 100, 99)
    positions = broker.portfolio()["positions"]
    assert len(positions) == 2
    assert {p["market"] for p in positions} == {"stocks", "crypto"}


def test_paper_broker_enforces_five_entry_daily_limit(tmp_path):
    from app.paper import PaperBroker, PaperTradeRejected

    broker = PaperBroker(str(tmp_path / "daily-limit.db"))
    for index in range(5):
        broker.place_order(f"STOCK{index}", "stocks", "buy", 1, 1000, 990)
    with pytest.raises(PaperTradeRejected, match="entry limit"):
        broker.place_order("STOCK5", "stocks", "buy", 1, 1000, 990)


def test_daily_report_calculates_realized_results_and_win_rate(tmp_path):
    broker = PaperBroker(str(tmp_path / "daily-report.db"))
    broker.place_order("WINNER", "stocks", "buy", 1, 100, 90)
    broker.place_order("WINNER", "stocks", "sell", 1, 110, reason="test_exit")
    broker.place_order("LOSER", "stocks", "buy", 1, 100, 90)
    broker.place_order("LOSER", "stocks", "sell", 1, 90, reason="test_exit")

    report = broker.daily_report()

    assert report["entries"] == 2
    assert report["closed_trades"] == 2
    assert report["wins"] == 1
    assert report["losses"] == 1
    assert report["win_rate_pct"] == 50.0
    assert report["realized_pnl"] < 0
    assert report["live_trading_enabled"] is False
