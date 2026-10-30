import json
from datetime import datetime
from pathlib import Path


class Outbox:
    """Stands in for real integrations (email, payments, escalation queue).
    Every side effect is appended to a JSON lines file so it can be inspected."""

    def __init__(self, path="data/outbox.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, kind, ticket_id, **data):
        entry = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "kind": kind,
            "ticket_id": ticket_id,
            **data,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def read_all(self):
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]
