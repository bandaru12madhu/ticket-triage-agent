from fastapi.testclient import TestClient

from app.graph import build_graph
from app.knowledge import KnowledgeBase
from app.main import create_app
from app.memory import CustomerMemory
from app.outbox import Outbox
from app.store import TicketStore
from tests.fakes import KB_DIR, ScriptedModel, action, classification

TICKET = {
    "subject": "Order arrived damaged",
    "body": "The jar is cracked and I want a refund.",
    "order_total": 64.5,
}


def make_client(tmp_path, actions, replies):
    model = ScriptedModel([classification() for _ in actions], actions, replies)
    outbox = Outbox(str(tmp_path / "outbox.jsonl"))
    memory = CustomerMemory(str(tmp_path / "memory.db"))
    graph = build_graph(model, KnowledgeBase(KB_DIR), outbox, memory=memory)
    store = TicketStore(str(tmp_path / "tickets.db"))
    app = create_app(graph=graph, store=store, memory=memory, data_dir=str(tmp_path))
    return TestClient(app), outbox


def test_health(tmp_path):
    client, _ = make_client(tmp_path, [], [])
    assert client.get("/health").json() == {"status": "ok"}


def test_refund_ticket_waits_then_resolves_after_review(tmp_path):
    client, outbox = make_client(tmp_path, [action("refund", 40.0, "damaged")], ["Draft"])

    created = client.post("/tickets", json=TICKET)
    assert created.status_code == 201
    body = created.json()
    assert body["status"] == "waiting_for_approval"
    assert body["proposed_action"]["type"] == "refund"
    assert body["draft_reply"] == "Draft"

    ticket_id = body["ticket_id"]
    reviewed = client.post("/tickets/" + ticket_id + "/review", json={"approved": True})
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "resolved"
    assert [e["kind"] for e in outbox.read_all()] == ["refund", "reply"]


def test_simple_ticket_is_answered_right_away(tmp_path):
    client, _ = make_client(tmp_path, [action("none")], ["Here is how to reset it."])
    body = client.post("/tickets", json=TICKET).json()
    assert body["status"] == "auto_replied"


def test_list_can_filter_by_status(tmp_path):
    client, _ = make_client(
        tmp_path,
        [action("refund", 10.0, "x"), action("none")],
        ["Draft one", "Draft two"],
    )
    client.post("/tickets", json=TICKET)
    client.post("/tickets", json=TICKET)

    assert len(client.get("/tickets").json()) == 2
    waiting = client.get("/tickets", params={"status": "waiting_for_approval"}).json()
    assert len(waiting) == 1
    assert waiting[0]["proposed_action"]["type"] == "refund"


def test_reviewing_twice_is_rejected(tmp_path):
    client, _ = make_client(tmp_path, [action("escalate", None, "angry")], ["Draft"])
    ticket_id = client.post("/tickets", json=TICKET).json()["ticket_id"]

    first = client.post("/tickets/" + ticket_id + "/review", json={"approved": False, "note": "no"})
    assert first.status_code == 200
    second = client.post("/tickets/" + ticket_id + "/review", json={"approved": True})
    assert second.status_code == 409


def test_unknown_ticket_returns_404(tmp_path):
    client, _ = make_client(tmp_path, [], [])
    assert client.get("/tickets/nope").status_code == 404
    assert client.post("/tickets/nope/review", json={"approved": True}).status_code == 404


def test_bad_ticket_is_rejected(tmp_path):
    client, _ = make_client(tmp_path, [], [])
    assert client.post("/tickets", json={"subject": "", "body": "text"}).status_code == 422
    assert client.post("/tickets", json={"subject": "hi", "body": "text", "order_total": -5}).status_code == 422


def test_second_ticket_shows_the_customer_history(tmp_path):
    client, _ = make_client(
        tmp_path,
        [action("none"), action("refund", 10.0, "damaged")],
        ["Reply one", "Reply two"],
    )
    ticket = {**TICKET, "customer_email": "sam@example.com"}

    first = client.post("/tickets", json=ticket).json()
    assert first["customer_history"] == []

    second = client.post("/tickets", json=ticket).json()
    assert second["status"] == "waiting_for_approval"
    assert len(second["customer_history"]) == 1
    assert second["customer_history"][0]["status"] == "auto_replied"


def test_history_endpoint_and_forget(tmp_path):
    client, _ = make_client(tmp_path, [action("none"), action("none")], ["One", "Two"])
    ticket = {**TICKET, "customer_email": "Sam@Example.com"}
    client.post("/tickets", json=ticket)
    client.post("/tickets", json=ticket)

    history = client.get("/customers/history", params={"email": "sam@example.com"}).json()
    assert len(history) == 2

    deleted = client.delete("/customers/history", params={"email": "sam@example.com"}).json()
    assert deleted == {"deleted": 2}
    assert client.get("/customers/history", params={"email": "sam@example.com"}).json() == []


def test_history_endpoint_needs_an_email(tmp_path):
    client, _ = make_client(tmp_path, [], [])
    assert client.get("/customers/history").status_code == 422
