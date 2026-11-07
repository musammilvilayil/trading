import pytest
from app.core import PaperPortfolio, RiskEngine, RiskRejected, Side, StrategyEngine, MockMarketData


def test_strategy_returns_valid_signal():
    result = StrategyEngine().analyze("BTC-USD", "crypto", MockMarketData().candles("BTC-USD"))
    assert result["signal"] in {"buy", "sell", "hold"}
    assert 0.5 <= result["confidence"] <= 0.85
    assert result["data_mode"] == "mock"


def test_risk_rejects_order_over_cap():
    book = PaperPortfolio()
    with pytest.raises(RiskRejected):
        RiskEngine().approve(side=Side.buy, quantity=1, price=3000,
                             stop_loss=2800, book=book)


def test_risk_requires_stop_loss():
    book = PaperPortfolio()
    with pytest.raises(RiskRejected):
        RiskEngine().approve(side=Side.buy, quantity=1, price=100,
                             stop_loss=None, book=book)


def test_risk_accepts_small_protected_paper_order():
    book = PaperPortfolio()
    RiskEngine().approve(side=Side.buy, quantity=1, price=100,
                         stop_loss=95, book=book)
