from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from .market import FEATURE_COLUMNS


@dataclass(frozen=True)
class TradeProposal:
    symbol: str
    action: str
    confidence: float
    entry: float
    atr: float
    reason: str


class TradingAgent:
    def __init__(self):
        self.model = HistGradientBoostingClassifier(max_depth=4, learning_rate=0.05, max_iter=150, random_state=42)
        self.trained = False

    def train(self, df: pd.DataFrame) -> None:
        if len(df) < 100:
            raise ValueError('Need at least 100 feature rows before training.')
        split = int(len(df) * 0.8)
        train = df.iloc[:split]
        self.model.fit(train[FEATURE_COLUMNS], train['target'])
        self.trained = True

    def propose(self, symbol: str, df: pd.DataFrame) -> TradeProposal:
        if not self.trained:
            raise RuntimeError('Agent must be trained first.')
        row = df.iloc[-1]
        p_up = float(self.model.predict_proba(df[FEATURE_COLUMNS].iloc[[-1]])[0][1])
        bullish = row['ema9'] > row['ema21'] and row['Close'] > row['vwap']
        bearish = row['ema9'] < row['ema21'] and row['Close'] < row['vwap']
        if p_up >= 0.5 and bullish:
            action, conf = 'BUY', p_up
        elif p_up < 0.5 and bearish:
            action, conf = 'SELL', 1 - p_up
        else:
            action, conf = 'WAIT', max(p_up, 1-p_up)
        return TradeProposal(symbol, action, conf, float(row['Close']), float(row['atr14']), f'p_up={p_up:.3f}; EMA/VWAP confirmation={bullish or bearish}')
