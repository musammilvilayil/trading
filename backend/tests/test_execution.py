import pytest
from app.execution import build_paper_buy_plan


def test_order_plan_converts_quote_to_inr_and_respects_risk_cap():
    plan = build_paper_buy_plan({"entry": 100, "atr": 2}, 25000, 25000, 25000, 83, "crypto")
    assert plan is not None
    assert plan["entry_inr"] == 8300
    assert plan["max_loss_inr"] <= 125
    assert plan["quantity"] * plan["entry_inr"] <= 2500


def test_order_plan_rounds_stock_quantity_to_whole_shares():
    plan = build_paper_buy_plan({"entry": 100, "atr": 1}, 25000, 25000, 25000, 1, "stocks")
    assert plan is not None
    assert float(plan["quantity"]).is_integer()


def test_order_plan_fails_when_risk_budget_cannot_buy_minimum_lot():
    plan = build_paper_buy_plan({"entry": 100000, "atr": 500}, 25000, 25000, 25000, 1, "stocks")
    assert plan is None
