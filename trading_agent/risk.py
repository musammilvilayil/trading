from __future__ import annotations
from dataclasses import dataclass
from .agent import TradeProposal
from .config import settings


@dataclass(frozen=True)
class ApprovedOrder:
    symbol: str
    side: str
    quantity: int
    entry: float
    stop: float
    target: float
    max_loss: float


class RiskEngine:
    def approve(self, proposal: TradeProposal, equity: float, daily_pnl: float = 0) -> ApprovedOrder | None:
        if proposal.action not in {'BUY', 'SELL'} or proposal.confidence < settings.min_confidence:
            return None
        if daily_pnl <= -(equity * settings.max_daily_loss_pct):
            return None
        risk_budget = equity * settings.risk_per_trade_pct
        stop_distance = max(proposal.atr, proposal.entry * 0.002)
        qty_by_risk = int(risk_budget / stop_distance)
        qty_by_exposure = int(settings.max_position_inr / proposal.entry)
        qty = max(0, min(qty_by_risk, qty_by_exposure))
        if qty < 1:
            return None
        if proposal.action == 'BUY':
            stop = proposal.entry - stop_distance
            target = proposal.entry + stop_distance * settings.reward_risk_ratio
        else:
            stop = proposal.entry + stop_distance
            target = proposal.entry - stop_distance * settings.reward_risk_ratio
        return ApprovedOrder(proposal.symbol, proposal.action, qty, proposal.entry, stop, target, qty * stop_distance)
