import sqlite3
import threading
from datetime import datetime


class TicketStore:
    """Keeps a list of ticket ids so the API can list them.
    The ticket details themselves live in the graph checkpoints."""

    def __init__(self, path):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.Lock()
        with self.lock:
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS tickets "
                "(id TEXT PRIMARY KEY, subject TEXT, created_at TEXT)"
            )
            self.conn.commit()

    def add(self, ticket_id, subject):
        with self.lock:
            self.conn.execute(
                "INSERT INTO tickets (id, subject, created_at) VALUES (?, ?, ?)",
                (ticket_id, subject, datetime.now().isoformat(timespec="seconds")),
            )
            self.conn.commit()

    def ids(self):
        with self.lock:
            rows = self.conn.execute(
                "SELECT id FROM tickets ORDER BY created_at DESC, rowid DESC"
            ).fetchall()
        return [row[0] for row in rows]
