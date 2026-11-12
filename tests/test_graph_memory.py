from langgraph.types import Command

from app.graph import build_graph, history_text
from app.knowledge import KnowledgeBase
from app.memory import CustomerMemory
from app.outbox import Outbox
from tests.fakes import KB_DIR, ScriptedModel, action, classification


def make_ticket(ticket_id, email="sam@example.com", **changes):
    ticket = {
        "id": ticket_id,
        "subject": "Order arrived damaged",
        "body": "The jar is cracked and I want a refund.",
        "customer_email": email,
        "order_total": 64.5,
    }
    ticket.update(changes)
    return ticket


def config(ticket_id):
    return {"configurable": {"thread_id": ticket_id}}


def build(tmp_path, classifications, actions, replies):
    model = ScriptedModel(classifications, actions, replies)
    memory = CustomerMemory(str(tmp_path / "memory.db"))
    outbox = Outbox(str(tmp_path / "outbox.jsonl"))
    graph = build_graph(model, KnowledgeBase(KB_DIR), outbox, memory=memory)
    return graph, model, memory


def test_history_text_formats_entries():
    text = history_text(
        [{"created_at": "2026-11-01T10:00:00", "category": "billing", "summary": "Double charge",
          "action": "escalate", "status": "resolved"}]
    )
    assert "Earlier tickets from this customer" in text
    assert "2026-11-01, billing: Double charge" in text
    assert "result: resolved" in text
    assert history_text([]) == "No earlier tickets from this customer."


def test_finished_ticket_is_remembered(tmp_path):
    graph, model, memory = build(
        tmp_path, [classification(summary="Asked about shipping")], [action("none")], ["Reply"]
    )
    graph.invoke({"ticket": make_ticket("t1")}, config("t1"))

    items = memory.recent("sam@example.com")
    assert len(items) == 1
    assert items[0]["ticket_id"] == "t1"
    assert items[0]["summary"] == "Asked about shipping"
    assert items[0]["status"] == "auto_replied"


def test_second_ticket_sees_the_first_one(tmp_path):
    graph, model, memory = build(
        tmp_path,
        [classification(summary="Asked about password reset"), classification()],
        [action("none"), action("refund", 40.0, "damaged item")],
        ["First reply", "Second reply"],
    )
    graph.invoke({"ticket": make_ticket("t1")}, config("t1"))
    graph.invoke({"ticket": make_ticket("t2")}, config("t2"))

    snapshot = graph.get_state(config("t2"))
    assert snapshot.next == ("approval",)
    payload = snapshot.tasks[0].interrupts[0].value
    assert len(payload["customer_history"]) == 1
    assert payload["customer_history"][0]["summary"] == "Asked about password reset"
    assert any("Asked about password reset" in prompt for prompt in model.prompts)


def test_waiting_ticket_is_not_remembered_until_it_is_reviewed(tmp_path):
    graph, model, memory = build(
        tmp_path, [classification()], [action("refund", 40.0, "damaged item")], ["Reply"]
    )
    graph.invoke({"ticket": make_ticket("t1")}, config("t1"))
    assert memory.recent("sam@example.com") == []

    graph.invoke(Command(resume={"approved": True}), config("t1"))
    items = memory.recent("sam@example.com")
    assert len(items) == 1
    assert items[0]["status"] == "resolved"
    assert items[0]["action"] == "refund"


def test_rejected_ticket_is_remembered_as_rejected(tmp_path):
    graph, model, memory = build(
        tmp_path, [classification()], [action("refund", 40.0, "damaged item")], ["Reply"]
    )
    graph.invoke({"ticket": make_ticket("t1")}, config("t1"))
    graph.invoke(Command(resume={"approved": False, "note": "no photo"}), config("t1"))

    assert memory.recent("sam@example.com")[0]["status"] == "rejected"


def test_ticket_without_an_email_is_not_remembered(tmp_path):
    graph, model, memory = build(tmp_path, [classification()], [action("none")], ["Reply"])
    graph.invoke({"ticket": make_ticket("t1", email=None)}, config("t1"))

    values = graph.get_state(config("t1")).values
    assert values["status"] == "auto_replied"
    assert values["history"] == []
    assert memory.recent(None) == []


def test_other_customers_history_is_not_used(tmp_path):
    graph, model, memory = build(
        tmp_path,
        [classification(summary="Lee had a billing problem"), classification()],
        [action("none"), action("none")],
        ["Reply one", "Reply two"],
    )
    graph.invoke({"ticket": make_ticket("t1", email="lee@example.com")}, config("t1"))
    graph.invoke({"ticket": make_ticket("t2", email="sam@example.com")}, config("t2"))

    assert graph.get_state(config("t2")).values["history"] == []
    second_prompts = model.prompts[len(model.prompts) // 2:]
    assert not any("Lee had a billing problem" in prompt for prompt in second_prompts)


def test_forgotten_customer_has_no_history_next_time(tmp_path):
    graph, model, memory = build(
        tmp_path,
        [classification(), classification()],
        [action("none"), action("none")],
        ["Reply one", "Reply two"],
    )
    graph.invoke({"ticket": make_ticket("t1")}, config("t1"))
    assert memory.forget("sam@example.com") == 1
    graph.invoke({"ticket": make_ticket("t2")}, config("t2"))

    assert graph.get_state(config("t2")).values["history"] == []
