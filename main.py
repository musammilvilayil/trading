from rich import print
from trading_agent.agent import TradingAgent
from trading_agent.config import settings
from trading_agent.market import fetch_intraday, features
from trading_agent.risk import RiskEngine


def run(symbol: str = 'RELIANCE.NS'):
    raw = fetch_intraday(symbol)
    data = features(raw)
    agent = TradingAgent()
    agent.train(data)
    proposal = agent.propose(symbol, data)
    order = RiskEngine().approve(proposal, settings.starting_capital)
    print({'mode': 'PAPER' if settings.paper_trading else 'LIVE_DISABLED', 'proposal': proposal, 'approved_order': order})
    if not settings.paper_trading:
        raise RuntimeError('Live execution is intentionally not implemented in V1. Validate with paper trading/backtests first.')


if __name__ == '__main__':
    run()
