from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from .config import settings
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
    """Quantitative classifier with a configurable confidence gate.

    The confidence value is a model score, not a calibrated probability of profit.
    """

    def __init__(self):
        self.model = HistGradientBoostingClassifier(
            max_depth=4, learning_rate=0.05, max_iter=150, random_state=42
        )
        self.trained = False

    def train(self, df: pd.DataFrame) -> None:
        if len(df) < 100:
            raise ValueError("Need at least 100 feature rows before training.")
        data = df.sort_index().dropna(subset=FEATURE_COLUMNS + ["target"])
        split = int(len(data) * 0.8)
        train = data.iloc[:split]
        if len(train) < 80 or train["target"].nunique() < 2:
            raise ValueError("Training window needs at least 80 rows and both target classes.")
        self.model.fit(train[FEATURE_COLUMNS], train["target"].astype(int))
        self.trained = True

    def propose(self, symbol: str, df: pd.DataFrame) -> TradeProposal:
        if not self.trained:
            raise RuntimeError("Agent must be trained first.")
        data = df.sort_index().dropna(subset=FEATURE_COLUMNS + ["atr14", "ema9", "ema21", "vwap"])
        if data.empty:
            raise ValueError("No valid latest feature row is available.")
        row = data.iloc[-1]
        probabilities = self.model.predict_proba(data[FEATURE_COLUMNS].iloc[[-1]])[0]
        classes = list(self.model.classes_)
        up_index = classes.index(1) if 1 in classes else None
        if up_index is None:
            raise ValueError("The trained model has no positive target class.")
        p_up = float(probabilities[up_index])
        threshold = float(settings.min_confidence)
        if not 0.5 < threshold < 1:
            raise ValueError("MIN_CONFIDENCE must be between 0.5 and 1.")

        bullish = row["ema9"] > row["ema21"] and row["Close"] > row["vwap"]
        bearish = row["ema9"] < row["ema21"] and row["Close"] < row["vwap"]
        if p_up >= threshold and bullish:
            action, confidence = "BUY", p_up
        elif p_up <= 1 - threshold and bearish:
            action, confidence = "SELL", 1 - p_up
        else:
            action, confidence = "WAIT", max(p_up, 1 - p_up)

        return TradeProposal(
            symbol=symbol,
            action=action,
            confidence=confidence,
            entry=float(row["Close"]),
            atr=float(row["atr14"]),
            reason=(
                f"p_up={p_up:.3f}; threshold={threshold:.2f}; "
                f"EMA/VWAP confirmation={bullish or bearish}"
            ),
        )
