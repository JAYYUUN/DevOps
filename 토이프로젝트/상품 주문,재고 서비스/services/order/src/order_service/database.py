import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def connect(database_path: Path) -> Iterator[sqlite3.Connection]:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=10)
    connection.row_factory = sqlite3.Row
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
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                product_id TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                status TEXT NOT NULL CHECK (
                    status IN ('pending', 'confirmed', 'rejected')
                ),
                rejection_reason TEXT
            )
            """
        )


def create_order(
    database_path: Path,
    order_id: str,
    product_id: str,
    quantity: int,
) -> sqlite3.Row:
    with connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO orders (order_id, product_id, quantity, status)
            VALUES (?, ?, ?, 'pending')
            """,
            (order_id, product_id, quantity),
        )
        return connection.execute(
            "SELECT * FROM orders WHERE order_id = ?",
            (order_id,),
        ).fetchone()


def update_order_result(
    database_path: Path,
    order_id: str,
    status: str,
    rejection_reason: str | None,
) -> sqlite3.Row:
    with connect(database_path) as connection:
        connection.execute(
            """
            UPDATE orders
            SET status = ?, rejection_reason = ?
            WHERE order_id = ? AND status = 'pending'
            """,
            (status, rejection_reason, order_id),
        )
        return connection.execute(
            "SELECT * FROM orders WHERE order_id = ?",
            (order_id,),
        ).fetchone()


def get_order(database_path: Path, order_id: str) -> sqlite3.Row | None:
    with connect(database_path) as connection:
        return connection.execute(
            "SELECT * FROM orders WHERE order_id = ?",
            (order_id,),
        ).fetchone()
