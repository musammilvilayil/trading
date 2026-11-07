from __future__ import annotations

import math


def build_paper_buy_plan(proposal: dict, equity_inr: float, cash_inr: float,
                         initial_capital_inr: float, fx_to_inr: float,
                         market: str) -> dict | None:
    """Size a long paper order entirely in INR, including non-INR quote instruments."""
    entry = float(proposal["entry"])
    atr = float(proposal["atr"])
    if entry <= 0 or atr <= 0 or fx_to_inr <= 0 or equity_inr <= 0:
        return None
    entry_inr = entry * fx_to_inr
    stop_distance_inr = max(atr * fx_to_inr, entry_inr * 0.002)
    risk_budget = equity_inr * 0.005
    max_order = initial_capital_inr * 0.10
    max_exposure = initial_capital_inr * 0.50
    qty = min(risk_budget / stop_distance_inr, max_order / entry_inr,
              cash_inr / (entry_inr * 1.001))
    if market == "stocks":
        qty = math.floor(qty)
    else:
        qty = math.floor(qty * 1_000_000) / 1_000_000
    if qty <= 0:
        return None
    return {
        "quantity": qty,
        "entry_inr": round(entry_inr, 6),
        "stop_loss_inr": round(entry_inr - stop_distance_inr, 6),
        "max_loss_inr": round(qty * stop_distance_inr, 4),
        "fx_to_inr": round(fx_to_inr, 8),
        "quote_entry": entry,
        "max_order_inr": max_order,
        "max_exposure_inr": max_exposure
    }
