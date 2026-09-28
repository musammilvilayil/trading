from trading_agent.agent import TradeProposal
from trading_agent.risk import RiskEngine


def test_low_confidence_rejected():
    p = TradeProposal('TEST', 'BUY', 0.50, 100.0, 1.0, 'test')
    assert RiskEngine().approve(p, 25_000) is None


def test_daily_loss_kill_switch():
    p = TradeProposal('TEST', 'BUY', 0.90, 100.0, 1.0, 'test')
    assert RiskEngine().approve(p, 25_000, daily_pnl=-500) is None


def test_position_exposure_is_capped():
    p = TradeProposal('TEST', 'BUY', 0.90, 100.0, 1.0, 'test')
    order = RiskEngine().approve(p, 25_000)
    assert order is not None
    assert order.quantity * order.entry <= 3_000
