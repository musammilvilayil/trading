import pytest

from app.exit_manager import LongExitPolicy, evaluate_long_exit


def test_initial_stop_exits_without_profit_activation():
    result = evaluate_long_exit(
        entry_price=100, current_price=98, highest_price=100,
        current_stop=99, policy=LongExitPolicy(),
    )
    assert result["exit_triggered"] is True
    assert result["exit_reason"] == "initial_stop"
    assert result["effective_stop"] == 99


def test_break_even_stop_activates_after_small_profit():
    result = evaluate_long_exit(
        entry_price=100, current_price=101, highest_price=101,
        current_stop=95, policy=LongExitPolicy(),
    )
    assert result["break_even_active"] is True
    assert result["effective_stop"] == 100
    assert result["exit_triggered"] is False


def test_trailing_stop_ratchets_up_and_triggers_exit():
    policy = LongExitPolicy()
    raised = evaluate_long_exit(
        entry_price=100, current_price=102, highest_price=102,
        current_stop=95, policy=policy,
    )
    assert raised["trailing_active"] is True
    assert raised["effective_stop"] == pytest.approx(101.388)

    pulled_back = evaluate_long_exit(
        entry_price=100, current_price=101.3, highest_price=102,
        current_stop=raised["effective_stop"], policy=policy,
    )
    assert pulled_back["effective_stop"] == raised["effective_stop"]
    assert pulled_back["exit_triggered"] is True
    assert pulled_back["exit_reason"] == "trailing_stop"


def test_trailing_stop_never_moves_down():
    result = evaluate_long_exit(
        entry_price=100, current_price=101, highest_price=101,
        current_stop=99.5, policy=LongExitPolicy(),
    )
    assert result["effective_stop"] >= 99.5


def test_invalid_price_is_rejected():
    with pytest.raises(ValueError):
        evaluate_long_exit(
            entry_price=100, current_price=0, highest_price=100,
            current_stop=95,
        )
