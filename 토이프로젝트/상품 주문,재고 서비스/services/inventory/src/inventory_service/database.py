import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def connect(database_path: Path) -> Iterator[sqlite3.Connection]:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(database_path: Path) -> None:
    with connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS stock (
                product_id TEXT PRIMARY KEY,
                available_quantity INTEGER NOT NULL CHECK (available_quantity >= 0)
            );

            CREATE TABLE IF NOT EXISTS reservations (
                order_id TEXT PRIMARY KEY,
                product_id TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                status TEXT NOT NULL CHECK (status IN ('reserved', 'rejected')),
                reason TEXT
            );
            """
        )


def add_stock(database_path: Path, product_id: str, quantity: int) -> int:
    with connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO stock (product_id, available_quantity)
            VALUES (?, ?)
            ON CONFLICT(product_id) DO UPDATE
            SET available_quantity = available_quantity + excluded.available_quantity
            """,
            (product_id, quantity),
        )
        row = connection.execute(
            "SELECT available_quantity FROM stock WHERE product_id = ?",
            (product_id,),
        ).fetchone()
        return row["available_quantity"]


def get_available_quantity(database_path: Path, product_id: str) -> int:
    with connect(database_path) as connection:
        row = connection.execute(
            "SELECT available_quantity FROM stock WHERE product_id = ?",
            (product_id,),
        ).fetchone()
        return row["available_quantity"] if row else 0


def reserve_stock(
    database_path: Path,
    order_id: str,
    product_id: str,
    quantity: int,
) -> sqlite3.Row:
    with connect(database_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT * FROM reservations WHERE order_id = ?",
            (order_id,),
        ).fetchone()
        if existing:
            if (
                existing["product_id"] != product_id
                or existing["quantity"] != quantity
            ):
                raise ValueError("order_id was already used for a different request")
            return existing

        updated = connection.execute(
            """
            UPDATE stock
            SET available_quantity = available_quantity - ?
            WHERE product_id = ? AND available_quantity >= ?
            """,
            (quantity, product_id, quantity),
        )
        reserved = updated.rowcount == 1
        status = "reserved" if reserved else "rejected"
        reason = None if reserved else "insufficient_stock"
        connection.execute(
            """
            INSERT INTO reservations (order_id, product_id, quantity, status, reason)
            VALUES (?, ?, ?, ?, ?)
            """,
            (order_id, product_id, quantity, status, reason),
        )
        return connection.execute(
            "SELECT * FROM reservations WHERE order_id = ?",
            (order_id,),
        ).fetchone()
