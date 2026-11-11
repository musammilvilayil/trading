import pytest

from app.paper import PaperBroker


def test_paper_broker_moves_stop_to_break_even_and_trailing_stop(tmp_path):
    broker = PaperBroker(str(tmp_path / "paper.db"))
    broker.place_order("ABC", "stocks", "buy", 0.1, 1000, 990)

    protected = broker.process_price("ABC", "stocks", 1010)
    assert protected["break_even_active"] is True
    assert protected["stop_triggered"] is False
    assert protected["effective_stop"] > 990

    trailing = broker.process_price("ABC", "stocks", 1020)
    assert trailing["trailing_active"] is True
    assert trailing["effective_stop"] > protected["effective_stop"]

    exited = broker.process_price("ABC", "stocks", 1000)
    assert exited["stop_triggered"] is True
    assert exited["exit_reason"] == "trailing_stop"
    assert exited["order"]["side"] == "sell"
    assert broker.portfolio()["positions"] == []


def test_existing_positions_database_is_migrated_with_high_watermark(tmp_path):
    import sqlite3

    path = str(tmp_path / "legacy.db")
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE account (
              id INTEGER PRIMARY KEY CHECK(id=1), initial_capital REAL NOT NULL,
              cash REAL NOT NULL, realized_pnl REAL NOT NULL DEFAULT 0,
              day_start_equity REAL NOT NULL, day_key TEXT NOT NULL
            );
            CREATE TABLE positions (
              symbol TEXT PRIMARY KEY, market TEXT NOT NULL, quantity REAL NOT NULL,
              average_price REAL NOT NULL, last_price REAL NOT NULL, stop_loss REAL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE orders (
              id TEXT PRIMARY KEY, symbol TEXT NOT NULL, market TEXT NOT NULL,
              side TEXT NOT NULL, quantity REAL NOT NULL, price REAL NOT NULL,
              fee REAL NOT NULL, slippage REAL NOT NULL, realized_pnl REAL NOT NULL DEFAULT 0,
              status TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL
            );
            INSERT INTO account VALUES(1,25000,24000,0,25000,'2026-11-11');
            INSERT INTO positions VALUES('ABC','stocks',1,1000,1010,990,'2026-11-11T09:00:00+00:00');
        """)
    broker = PaperBroker(path)
    position = broker.portfolio()["positions"][0]
    assert position["high_watermark"] == 1010
    assert position["stop_loss"] == 990
