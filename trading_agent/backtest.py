from __future__ import annotations

from dataclasses import dataclass
import math
import pandas as pd


@dataclass(frozen=True)
class BacktestConfig:
    starting_cash: float = 25_000.0
    fee_rate: float = 0.001
    slippage_rate: float = 0.0005
    max_exposure_fraction: float = 0.50


def run_ema_backtest(candles: pd.DataFrame, config: BacktestConfig = BacktestConfig()) -> dict:
    """Long-only EMA crossover simulation.

    Signals are computed at candle close and executed at the next candle open.
    Fees and adverse slippage are charged on both entries and exits.
    """
    required = {"Open", "High", "Low", "Close", "Volume"}
    if not required.issubset(candles.columns):
        raise ValueError(f"Missing candle columns: {sorted(required - set(candles.columns))}")
    if len(candles) < 30:
        raise ValueError("At least 30 candles are required.")
    data = candles.copy().sort_index()
    close = data["Close"].astype(float)
    data["fast"] = close.ewm(span=9, adjust=False).mean()
    data["slow"] = close.ewm(span=21, adjust=False).mean()
    data["signal"] = (data["fast"] > data["slow"]).astype(int)
    cash = config.starting_cash
    qty = 0.0
    entry_price = 0.0
    entry_cost = 0.0
    trades: list[dict] = []
    equity_curve: list[float] = [config.starting_cash]

    for i in range(1, len(data) - 1):
        prior_signal = int(data["signal"].iloc[i - 1])
        current_signal = int(data["signal"].iloc[i])
        next_open = float(data["Open"].iloc[i + 1])
        if not math.isfinite(next_open) or next_open <= 0:
            continue

        if qty == 0 and prior_signal == 0 and current_signal == 1:
            execution = next_open * (1 + config.slippage_rate)
            budget = min(cash, config.starting_cash * config.max_exposure_fraction)
            qty = budget / (execution * (1 + config.fee_rate))
            if qty > 0:
                entry_price = execution
                entry_cost = qty * execution * (1 + config.fee_rate)
                cash -= entry_cost
        elif qty > 0 and prior_signal == 1 and current_signal == 0:
            execution = next_open * (1 - config.slippage_rate)
            proceeds = qty * execution * (1 - config.fee_rate)
            pnl = proceeds - entry_cost
            cash += proceeds
            trades.append({"entry_price": entry_price, "exit_price": execution,
                           "quantity": qty, "net_pnl": pnl})
            qty = 0.0
            entry_price = 0.0
            entry_cost = 0.0

        mark = float(data["Close"].iloc[i + 1])
        equity_curve.append(cash + qty * mark)

    if qty > 0:
        last = float(data["Close"].iloc[-1])
        execution = last * (1 - config.slippage_rate)
        proceeds = qty * execution * (1 - config.fee_rate)
        pnl = proceeds - entry_cost
        cash += proceeds
        trades.append({"entry_price": entry_price, "exit_price": execution,
                       "quantity": qty, "net_pnl": pnl})
        qty = 0.0

    equity_curve.append(cash)
    series = pd.Series(equity_curve, dtype=float)
    peaks = series.cummax()
    drawdowns = (series / peaks) - 1
    returns = series.pct_change().dropna()
    sharpe = 0.0
    if len(returns) > 1 and returns.std(ddof=1) > 0:
        sharpe = float((returns.mean() / returns.std(ddof=1)) * math.sqrt(252))
    wins = sum(1 for trade in trades if trade["net_pnl"] > 0)
    final_equity = float(series.iloc[-1])
    return {
        "starting_cash": config.starting_cash,
        "final_equity": round(final_equity, 2),
        "total_return_pct": round((final_equity / config.starting_cash - 1) * 100, 3),
        "max_drawdown_pct": round(float(drawdowns.min()) * 100, 3),
        "sharpe_ratio": round(sharpe, 3),
        "closed_trades": len(trades),
        "win_rate_pct": round(wins / len(trades) * 100, 2) if trades else 0.0,
        "net_pnl": round(final_equity - config.starting_cash, 2),
        "equity_curve": [round(float(value), 2) for value in series.tolist()],
        "trades": [{**trade, "net_pnl": round(trade["net_pnl"], 2)} for trade in trades],
        "execution_assumptions": {"fee_rate": config.fee_rate,
                                  "slippage_rate": config.slippage_rate,
                                  "signal_execution": "next candle open"},
        "disclaimer": "Historical simulation only; fees, slippage and future market conditions may differ."
    }
