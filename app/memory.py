import sqlite3
import threading
from datetime import datetime


def clean_email(email):
    if not email:
        return ""
    return email.strip().lower()


class NoMemory:
    """Used when memory is switched off. It remembers nothing."""

    def recent(self, email, limit=5):
        return []

    def add(self, email, entry):
        return None

    def forget(self, email):
        return 0


class CustomerMemory:
    """Long-term memory. It keeps a short record of every finished ticket for each
    customer, so a new ticket from the same person can see what happened before.
    This is different from the graph checkpoints, which only save one ticket's
    progress so it can continue after a restart."""

    def __init__(self, path):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.Lock()
        with self.lock:
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS customer_history ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "email TEXT NOT NULL, ticket_id TEXT, created_at TEXT, "
                "category TEXT, summary TEXT, action TEXT, status TEXT)"
            )
            self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_history_email ON customer_history (email)"
            )
            self.conn.commit()

    def add(self, email, entry):
        email = clean_email(email)
        if not email:
            return
        with self.lock:
            self.conn.execute(
                "INSERT INTO customer_history "
                "(email, ticket_id, created_at, category, summary, action, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    email,
                    entry["ticket_id"],
                    datetime.now().isoformat(timespec="seconds"),
                    entry["category"],
                    entry["summary"],
                    entry["action"],
                    entry["status"],
                ),
            )
            self.conn.commit()

    def recent(self, email, limit=5):
        """Newest first."""
        email = clean_email(email)
        if not email:
            return []
        with self.lock:
            rows = self.conn.execute(
                "SELECT ticket_id, created_at, category, summary, action, status "
                "FROM customer_history WHERE email = ? ORDER BY id DESC LIMIT ?",
                (email, limit),
            ).fetchall()
        keys = ("ticket_id", "created_at", "category", "summary", "action", "status")
        return [dict(zip(keys, row)) for row in rows]

    def forget(self, email):
        """Delete everything stored for one customer. Returns how many records went."""
        email = clean_email(email)
        if not email:
            return 0
        with self.lock:
            cursor = self.conn.execute("DELETE FROM customer_history WHERE email = ?", (email,))
            self.conn.commit()
            return cursor.rowcount
