from langgraph.types import Command

from app.graph import build_graph
from app.knowledge import KnowledgeBase
from app.outbox import Outbox
from tests.fakes import KB_DIR, ScriptedModel, action, classification

CONFIG = {"configurable": {"thread_id": "t1"}}


def make_ticket(**changes):
    ticket = {
        "id": "t1",
        "subject": "Order arrived damaged",
        "body": "The jar is cracked and I want a refund.",
        "customer_email": None,
        "order_total": 64.5,
    }
    ticket.update(changes)
    return ticket


def make_graph(tmp_path, proposed, replies=("Draft reply",)):
    model = ScriptedModel([classification()], [proposed], list(replies))
    outbox = Outbox(str(tmp_path / "outbox.jsonl"))
    return build_graph(model, KnowledgeBase(KB_DIR), outbox), outbox


def kinds(outbox):
    return [entry["kind"] for entry in outbox.read_all()]


def test_simple_ticket_is_answered_without_approval(tmp_path):
    graph, outbox = make_graph(tmp_path, action("none"))
    graph.invoke({"ticket": make_ticket()}, CONFIG)

    snapshot = graph.get_state(CONFIG)
    assert not snapshot.next
    assert snapshot.values["status"] == "auto_replied"
    assert kinds(outbox) == ["reply"]


def test_refund_pauses_and_nothing_happens_before_approval(tmp_path):
    graph, outbox = make_graph(tmp_path, action("refund", 40.0, "damaged item"))
    graph.invoke({"ticket": make_ticket()}, CONFIG)

    snapshot = graph.get_state(CONFIG)
    assert snapshot.next == ("approval",)
    payload = snapshot.tasks[0].interrupts[0].value
    assert payload["proposed_action"]["type"] == "refund"
    assert payload["draft_reply"] == "Draft reply"
    assert kinds(outbox) == []


def test_approved_refund_is_executed_and_reply_sent(tmp_path):
    graph, outbox = make_graph(tmp_path, action("refund", 40.0, "damaged item"))
    graph.invoke({"ticket": make_ticket()}, CONFIG)
    graph.invoke(Command(resume={"approved": True, "note": "photo checked"}), CONFIG)

    values = graph.get_state(CONFIG).values
    assert values["status"] == "resolved"
    assert kinds(outbox) == ["refund", "reply"]
    assert outbox.read_all()[0]["amount"] == 40.0


def test_edited_reply_replaces_the_draft(tmp_path):
    graph, outbox = make_graph(tmp_path, action("escalate", None, "angry customer"))
    graph.invoke({"ticket": make_ticket()}, CONFIG)
    graph.invoke(Command(resume={"approved": True, "edited_reply": "A manager will call you."}), CONFIG)

    entries = outbox.read_all()
    assert [e["kind"] for e in entries] == ["escalation", "reply"]
    assert entries[1]["text"] == "A manager will call you."


def test_rejected_ticket_is_held_and_nothing_is_executed(tmp_path):
    graph, outbox = make_graph(tmp_path, action("refund", 40.0, "damaged item"))
    graph.invoke({"ticket": make_ticket()}, CONFIG)
    graph.invoke(Command(resume={"approved": False, "note": "no photo"}), CONFIG)

    values = graph.get_state(CONFIG).values
    assert values["status"] == "rejected"
    assert kinds(outbox) == ["held"]


def test_refund_larger_than_order_total_is_capped(tmp_path):
    graph, outbox = make_graph(tmp_path, action("refund", 500.0, "damaged item"))
    graph.invoke({"ticket": make_ticket(order_total=64.5)}, CONFIG)

    proposed = graph.get_state(CONFIG).values["action"]
    assert proposed["amount"] == 64.5


def test_refund_without_amount_is_escalated(tmp_path):
    graph, outbox = make_graph(tmp_path, action("refund", None, "damaged item"))
    graph.invoke({"ticket": make_ticket()}, CONFIG)

    proposed = graph.get_state(CONFIG).values["action"]
    assert proposed["type"] == "escalate"
