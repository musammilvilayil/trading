import numpy as np
import pandas as pd

from trading_agent.agent import TradingAgent
from trading_agent.config import settings


class FixedProbabilityModel:
    classes_ = np.array([0, 1])

    def __init__(self, p_up):
        self.p_up = p_up

    def predict_proba(self, frame):
        return np.array([[1 - self.p_up, self.p_up]])


def make_features(bullish=True):
    return pd.DataFrame([{
        "ret1": 0.01,
        "ema9": 101.0 if bullish else 99.0,
        "ema21": 100.0,
        "rsi14": 60.0,
        "atr14": 1.2,
        "vwap": 100.0,
        "volume_z": 1.0,
        "Close": 102.0 if bullish else 98.0,
        "target": 1.0,
    }], index=pd.to_datetime(["2026-11-11T09:30:00Z"]))


def test_agent_waits_when_model_score_is_below_configured_threshold(monkeypatch):
    monkeypatch.setattr(settings, "min_confidence", 0.62)
    agent = TradingAgent()
    agent.model = FixedProbabilityModel(0.58)
    agent.trained = True

    proposal = agent.propose("RELIANCE", make_features(bullish=True))

    assert proposal.action == "WAIT"


def test_agent_requires_both_confidence_and_bullish_confirmation(monkeypatch):
    monkeypatch.setattr(settings, "min_confidence", 0.62)
    agent = TradingAgent()
    agent.model = FixedProbabilityModel(0.75)
    agent.trained = True

    proposal = agent.propose("RELIANCE", make_features(bullish=True))

    assert proposal.action == "BUY"
    assert proposal.confidence == 0.75


def test_agent_sell_signal_requires_bearish_confirmation(monkeypatch):
    monkeypatch.setattr(settings, "min_confidence", 0.62)
    agent = TradingAgent()
    agent.model = FixedProbabilityModel(0.20)
    agent.trained = True

    proposal = agent.propose("RELIANCE", make_features(bullish=False))

    assert proposal.action == "SELL"
    assert proposal.confidence == 0.8
