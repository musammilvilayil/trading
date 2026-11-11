from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from .exit_manager import LongExitPolicy, evaluate_long_exit


class PaperTradeRejected(ValueError):
    pass


class PaperBroker:
    """SQLite-backed paper broker. Never connects to a real broker."""

    def __init__(self, db_path: str | None = None, initial_capital: float = 25_000):
        self.db_path = db_path or os.getenv("ATLAS_DB_PATH", "data/atlas.sqlite3")
        self.initial_capital = float(initial_capital)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _initialize(self):
        with self._connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS account (
              id INTEGER PRIMARY KEY CHECK(id=1),
              initial_capital REAL NOT NULL,
              cash REAL NOT NULL,
              realized_pnl REAL NOT NULL DEFAULT 0,
              day_start_equity REAL NOT NULL,
              day_key TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS positions (
              symbol TEXT NOT NULL, market TEXT NOT NULL, quantity REAL NOT NULL,
              average_price REAL NOT NULL, last_price REAL NOT NULL, stop_loss REAL,
              high_watermark REAL NOT NULL DEFAULT 0,
              updated_at TEXT NOT NULL,
              PRIMARY KEY(market, symbol)
            );
            CREATE TABLE IF NOT EXISTS orders (
              id TEXT PRIMARY KEY, symbol TEXT NOT NULL, market TEXT NOT NULL,
              side TEXT NOT NULL, quantity REAL NOT NULL, price REAL NOT NULL,
              fee REAL NOT NULL, slippage REAL NOT NULL, realized_pnl REAL NOT NULL DEFAULT 0,
              status TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);
            """)
            position_info = db.execute("PRAGMA table_info(positions)").fetchall()
            primary_key_columns = [row["name"] for row in sorted(position_info, key=lambda item: item["pk"]) if row["pk"]]
            if primary_key_columns == ["symbol"]:
                db.execute("ALTER TABLE positions RENAME TO positions_legacy")
                db.execute("""CREATE TABLE positions (
                    symbol TEXT NOT NULL, market TEXT NOT NULL, quantity REAL NOT NULL,
                    average_price REAL NOT NULL, last_price REAL NOT NULL, stop_loss REAL,
                    high_watermark REAL NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL, PRIMARY KEY(market, symbol)
                )""")
                db.execute("""INSERT OR IGNORE INTO positions
                    (symbol, market, quantity, average_price, last_price, stop_loss, high_watermark, updated_at)
                    SELECT symbol, market, quantity, average_price, last_price, stop_loss, last_price, updated_at
                    FROM positions_legacy""")
                db.execute("DROP TABLE positions_legacy")
            elif "high_watermark" not in {row["name"] for row in position_info}:
                db.execute("ALTER TABLE positions ADD COLUMN high_watermark REAL NOT NULL DEFAULT 0")
                db.execute("UPDATE positions SET high_watermark=last_price WHERE high_watermark=0")
            db.execute("INSERT OR IGNORE INTO account(id,initial_capital,cash,day_start_equity,day_key) VALUES(1,?,?,?,?)",
                       (self.initial_capital, self.initial_capital, self.initial_capital,
                        datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()))

    def _equity(self, db):
        row = db.execute("SELECT cash FROM account WHERE id=1").fetchone()
        market_value = db.execute("SELECT COALESCE(SUM(quantity*last_price),0) AS value FROM positions").fetchone()["value"]
        return float(row["cash"] + market_value)

    def portfolio(self):
        with self._connect() as db:
            account = db.execute("SELECT * FROM account WHERE id=1").fetchone()
            positions = [dict(row) for row in db.execute("SELECT * FROM positions ORDER BY symbol").fetchall()]
            orders = [dict(row) for row in db.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT 20").fetchall()]
            equity = self._equity(db)
            unrealized = sum((p["last_price"] - p["average_price"]) * p["quantity"] for p in positions)
            return {
                "capital": account["initial_capital"], "cash": round(account["cash"], 2),
                "invested_value": round(sum(p["quantity"] * p["last_price"] for p in positions), 2),
                "equity": round(equity, 2), "realized_pnl": round(account["realized_pnl"], 2),
                "unrealized_pnl": round(unrealized, 2), "total_pnl": round(equity-account["initial_capital"], 2),
                "positions": positions, "recent_orders": orders,
                "mode": "paper", "live_trading_enabled": False
            }

    def _daily_guard(self, db, equity: float):
        account = db.execute("SELECT * FROM account WHERE id=1").fetchone()
        today = datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()
        baseline = account["day_start_equity"]
        if account["day_key"] != today:
            baseline = equity
            db.execute("UPDATE account SET day_key=?, day_start_equity=? WHERE id=1", (today, baseline))
        if equity <= baseline * 0.98:
            raise PaperTradeRejected("Daily 2% drawdown guard is active; new buys are blocked.")

    def place_order(self, symbol: str, market: str, side: str, quantity: float,
                    reference_price: float, stop_loss: float | None = None,
                    reason: str = "manual_paper_order"):
        symbol, side = symbol.strip().upper(), side.lower()
        if not symbol or side not in {"buy", "sell"} or quantity <= 0 or reference_price <= 0:
            raise PaperTradeRejected("Invalid symbol, side, quantity or price.")
        if side == "buy" and (stop_loss is None or not 0 < stop_loss < reference_price):
            raise PaperTradeRejected("A valid stop-loss below the buy price is required.")
        fee_rate, slip_rate = 0.001, 0.0005
        execution_price = reference_price * (1 + slip_rate if side == "buy" else 1 - slip_rate)
        notional = quantity * execution_price
        fee = notional * fee_rate
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            account = db.execute("SELECT * FROM account WHERE id=1").fetchone()
            equity = self._equity(db)
            if side == "buy":
                self._daily_guard(db, equity)
            if side == "buy" and notional > account["initial_capital"] * 0.10:
                raise PaperTradeRejected("Buy order exceeds 10% of initial paper capital.")
            realized = 0.0
            if side == "buy":
                estimated_stop_fill = stop_loss * (1 - slip_rate)
                estimated_round_trip_cost = (
                    (execution_price - estimated_stop_fill) * quantity
                    + fee
                    + estimated_stop_fill * quantity * fee_rate
                )
                if estimated_round_trip_cost > equity * 0.005:
                    raise PaperTradeRejected(
                        "Estimated stop-loss risk including fees and slippage exceeds 0.5% of current equity."
                    )
                if notional + fee > account["cash"]:
                    raise PaperTradeRejected("Insufficient paper cash.")
                exposure = db.execute("SELECT COALESCE(SUM(quantity*last_price),0) AS value FROM positions").fetchone()["value"]
                if exposure + notional > account["initial_capital"] * 0.50:
                    raise PaperTradeRejected("Portfolio exposure would exceed 50% of initial capital.")
                old = db.execute("SELECT * FROM positions WHERE market=? AND symbol=?", (market, symbol)).fetchone()
                if old:
                    total = old["quantity"] + quantity
                    avg = (old["quantity"] * old["average_price"] + quantity * execution_price + fee) / total
                    effective_stop = max(old["stop_loss"] or 0, stop_loss)
                    high_watermark = max(old["high_watermark"], reference_price)
                    db.execute("""UPDATE positions SET quantity=?,average_price=?,last_price=?,stop_loss=?,
                               high_watermark=?,updated_at=? WHERE market=? AND symbol=?""",
                               (total, avg, reference_price, effective_stop, high_watermark, now, market, symbol))
                else:
                    db.execute("""INSERT INTO positions
                               (symbol,market,quantity,average_price,last_price,stop_loss,high_watermark,updated_at)
                               VALUES(?,?,?,?,?,?,?,?)""",
                               (symbol, market, quantity, execution_price + fee / quantity,
                                reference_price, stop_loss, reference_price, now))
                db.execute("UPDATE account SET cash=cash-? WHERE id=1", (notional + fee,))
            else:
                old = db.execute("SELECT * FROM positions WHERE market=? AND symbol=?", (market, symbol)).fetchone()
                if old is None or old["quantity"] + 1e-12 < quantity:
                    raise PaperTradeRejected("Insufficient paper position to sell.")
                realized = (execution_price - old["average_price"]) * quantity - fee
                remaining = old["quantity"] - quantity
                if remaining <= 1e-12:
                    db.execute("DELETE FROM positions WHERE market=? AND symbol=?", (market, symbol))
                else:
                    db.execute("UPDATE positions SET quantity=?,last_price=?,updated_at=? WHERE market=? AND symbol=?",
                               (remaining, reference_price, now, market, symbol))
                db.execute("UPDATE account SET cash=cash+?,realized_pnl=realized_pnl+? WHERE id=1",
                           (notional - fee, realized))
            order_id = f"PAPER-{uuid4().hex[:12].upper()}"
            db.execute("INSERT INTO orders VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                       (order_id, symbol, market, side, quantity, execution_price, fee,
                        abs(execution_price-reference_price)*quantity, realized,
                        "filled_simulated", reason, now))
            return {"id": order_id, "symbol": symbol, "market": market, "side": side,
                    "quantity": quantity, "price": round(execution_price, 6),
                    "fee": round(fee, 4), "realized_pnl": round(realized, 4),
                    "status": "filled_simulated", "created_at": now}

    def process_price(self, symbol: str, market: str, price: float):
        """Update a mark and execute a triggered protective exit atomically."""
        if price <= 0:
            raise PaperTradeRejected("Price must be positive.")
        symbol = symbol.strip().upper()
        fee_rate, slip_rate = 0.001, 0.0005
        now = datetime.now(timezone.utc).isoformat()

        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            position = db.execute(
                "SELECT * FROM positions WHERE market=? AND symbol=?", (market, symbol)
            ).fetchone()
            if not position:
                return {"symbol": symbol, "updated": False, "reason": "no_open_position"}
            if position["stop_loss"] is None:
                raise PaperTradeRejected(
                    "This legacy position has no stop-loss. Review and close it manually."
                )

            decision = evaluate_long_exit(
                entry_price=float(position["average_price"]),
                current_price=float(price),
                highest_price=float(position["high_watermark"] or position["last_price"]),
                current_stop=float(position["stop_loss"]),
                policy=LongExitPolicy(),
            )
            db.execute(
                """UPDATE positions SET last_price=?,stop_loss=?,high_watermark=?,updated_at=?
                   WHERE market=? AND symbol=?""",
                (price, decision["effective_stop"], decision["high_watermark"],
                 now, market, symbol),
            )
            quantity = float(position["quantity"])

            if not decision["exit_triggered"]:
                return {
                    "symbol": symbol, "updated": True, "stop_triggered": False,
                    "effective_stop": decision["effective_stop"],
                    "high_watermark": decision["high_watermark"],
                    "break_even_active": decision["break_even_active"],
                    "trailing_active": decision["trailing_active"],
                }

            # Keep the position mark, cash update, order journal and deletion in
            # one SQLite transaction so concurrent price ticks cannot double-sell.
            execution_price = price * (1 - slip_rate)
            notional = quantity * execution_price
            fee = notional * fee_rate
            realized = (execution_price - float(position["average_price"])) * quantity - fee
            db.execute(
                "UPDATE account SET cash=cash+?,realized_pnl=realized_pnl+? WHERE id=1",
                (notional - fee, realized),
            )
            db.execute(
                "DELETE FROM positions WHERE market=? AND symbol=?", (market, symbol)
            )
            order_id = f"PAPER-{uuid4().hex[:12].upper()}"
            db.execute(
                "INSERT INTO orders VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (order_id, symbol, market, "sell", quantity, execution_price, fee,
                 abs(execution_price - price) * quantity, realized,
                 "filled_simulated", f"protective_exit:{decision['exit_reason']}", now),
            )
            order = {
                "id": order_id, "symbol": symbol, "market": market, "side": "sell",
                "quantity": quantity, "price": round(execution_price, 6),
                "fee": round(fee, 4), "realized_pnl": round(realized, 4),
                "status": "filled_simulated", "created_at": now,
            }
            return {
                "symbol": symbol, "updated": True, "stop_triggered": True,
                "exit_reason": decision["exit_reason"],
                "effective_stop": decision["effective_stop"], "order": order,
            }
