import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "watchlist.db")


def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Create and return a database connection with row factory configured."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initialize SQLite database with watchlist and price_history tables."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            target_price_inr REAL NOT NULL,
            current_price_inr REAL DEFAULT 0.0,
            effective_price_inr REAL DEFAULT 0.0,
            coupon_notes TEXT DEFAULT '',
            status TEXT DEFAULT 'Watching',
            buy_link TEXT DEFAULT '',
            last_checked TEXT DEFAULT ''
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            price_inr REAL NOT NULL,
            checked_at TEXT NOT NULL,
            FOREIGN KEY (item_id) REFERENCES watchlist (id) ON DELETE CASCADE
        )
        """
    )

    conn.commit()
    conn.close()


def add_item(name: str, target_price: float, db_path: str = DEFAULT_DB_PATH) -> int:
    """Add a new item to watchlist. Returns the newly created item id."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO watchlist (item_name, target_price_inr, current_price_inr, effective_price_inr, coupon_notes, status, buy_link, last_checked)
        VALUES (?, ?, 0.0, 0.0, '', 'Watching', '', '')
        """,
        (name.strip(), float(target_price)),
    )
    item_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return item_id


def get_all_items(db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Retrieve all items from the watchlist."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM watchlist ORDER BY id DESC")
    rows = cursor.fetchall()
    items = [dict(row) for row in rows]
    conn.close()
    return items


def get_watching_items(db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Retrieve only items currently in 'Watching' status."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM watchlist WHERE status = 'Watching' ORDER BY id ASC")
    rows = cursor.fetchall()
    items = [dict(row) for row in rows]
    conn.close()
    return items


def update_item_price(
    item_id: int,
    current_price: float,
    effective_price: float,
    coupon_notes: str,
    buy_link: str,
    status: str = "Watching",
    db_path: str = DEFAULT_DB_PATH,
) -> None:
    """Update tracked item's current/effective price, notes, link, and record history."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute(
        """
        UPDATE watchlist
        SET current_price_inr = ?,
            effective_price_inr = ?,
            coupon_notes = ?,
            buy_link = ?,
            status = ?,
            last_checked = ?
        WHERE id = ?
        """,
        (
            float(current_price),
            float(effective_price),
            str(coupon_notes),
            str(buy_link),
            str(status),
            now_str,
            int(item_id),
        ),
    )

    # Insert into price history if price is valid positive number
    if effective_price > 0:
        cursor.execute(
            """
            INSERT INTO price_history (item_id, price_inr, checked_at)
            VALUES (?, ?, ?)
            """,
            (int(item_id), float(effective_price), now_str),
        )

    conn.commit()
    conn.close()


def reset_item_status(item_id: int, db_path: str = DEFAULT_DB_PATH) -> None:
    """Reset item status back to 'Watching'."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE watchlist
        SET status = 'Watching'
        WHERE id = ?
        """,
        (int(item_id),),
    )
    conn.commit()
    conn.close()

def delete_item(item_id: int, db_path: str = DEFAULT_DB_PATH) -> None:
    """Delete an item and its price history from the database."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM price_history WHERE item_id = ?", (int(item_id),))
    cursor.execute("DELETE FROM watchlist WHERE id = ?", (int(item_id),))
    conn.commit()
    conn.close()


def get_price_history(item_id: int, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """Retrieve chronological price history for an item."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, item_id, price_inr, checked_at
        FROM price_history
        WHERE item_id = ?
        ORDER BY checked_at ASC, id ASC
        """,
        (int(item_id),),
    )
    rows = cursor.fetchall()
    history = [dict(row) for row in rows]
    conn.close()
    return history


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DEFAULT_DB_PATH)
