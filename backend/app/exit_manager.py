from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class LongExitPolicy:
    """Deterministic protective-exit defaults for paper-traded long positions."""

    break_even_activation_pct: float = 0.008
    trailing_activation_pct: float = 0.012
    trailing_distance_pct: float = 0.006

    def as_dict(self) -> dict:
        return asdict(self)


def evaluate_long_exit(
    *,
    entry_price: float,
    current_price: float,
    highest_price: float,
    current_stop: float,
    policy: LongExitPolicy | None = None,
) -> dict:
    """Ratchet a long stop upward; never loosen an existing protective stop.

    Prices are simulated marks. Real execution can differ because of gaps,
    liquidity, latency, broker rules and slippage.
    """
    policy = policy or LongExitPolicy()
    if min(entry_price, current_price, highest_price, current_stop) <= 0:
        raise ValueError("All prices and the current stop must be positive.")
    if not 0 < policy.break_even_activation_pct < 1:
        raise ValueError("Break-even activation must be between 0 and 1.")
    if not 0 < policy.trailing_activation_pct < 1:
        raise ValueError("Trailing activation must be between 0 and 1.")
    if not 0 < policy.trailing_distance_pct < 1:
        raise ValueError("Trailing distance must be between 0 and 1.")

    high_watermark = max(highest_price, current_price, entry_price)
    effective_stop = current_stop
    break_even_active = high_watermark >= entry_price * (1 + policy.break_even_activation_pct)
    trailing_active = high_watermark >= entry_price * (1 + policy.trailing_activation_pct)

    if break_even_active:
        effective_stop = max(effective_stop, entry_price)
    if trailing_active:
        effective_stop = max(
            effective_stop,
            high_watermark * (1 - policy.trailing_distance_pct),
        )

    exit_triggered = current_price <= effective_stop
    if exit_triggered and trailing_active:
        exit_reason = "trailing_stop"
    elif exit_triggered and break_even_active and effective_stop >= entry_price:
        exit_reason = "break_even_stop"
    elif exit_triggered:
        exit_reason = "initial_stop"
    else:
        exit_reason = None

    return {
        "high_watermark": round(high_watermark, 8),
        "effective_stop": round(effective_stop, 8),
        "break_even_active": break_even_active,
        "trailing_active": trailing_active,
        "exit_triggered": exit_triggered,
        "exit_reason": exit_reason,
    }


def risk_policy_summary() -> dict:
    exits = LongExitPolicy()
    return {
        "mode": "paper_only",
        "live_trading_enabled": False,
        "risk_per_trade_fraction": 0.005,
        "daily_drawdown_fraction": 0.02,
        "max_buy_order_fraction_of_initial_capital": 0.10,
        "max_gross_exposure_fraction_of_initial_capital": 0.50,
        "long_exit_policy": exits.as_dict(),
        "notes": [
            "Stops are simulated against incoming price marks; they are not guaranteed fill prices.",
            "Gap risk, slippage, liquidity and broker/network failures can exceed planned loss.",
            "This policy does not establish profitability or an 80% win probability.",
        ],
    }
