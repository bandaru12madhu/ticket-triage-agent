from app.graph import clean_action
from app.outbox import Outbox
from app.store import TicketStore


def test_none_action_keeps_no_amount():
    out = clean_action({"type": "none", "amount": 5.0, "reason": "x"})
    assert out["amount"] is None


def test_refund_is_capped_at_order_total():
    out = clean_action({"type": "refund", "amount": 500.0, "reason": "damaged"}, order_total=64.5)
    assert out["type"] == "refund"
    assert out["amount"] == 64.5


def test_refund_without_amount_becomes_escalation():
    out = clean_action({"type": "refund", "amount": None, "reason": "damaged"})
    assert out["type"] == "escalate"
    assert "amount is unclear" in out["reason"]


def test_refund_with_zero_amount_becomes_escalation():
    out = clean_action({"type": "refund", "amount": 0, "reason": "damaged"})
    assert out["type"] == "escalate"


def test_valid_refund_is_rounded_and_kept():
    out = clean_action({"type": "refund", "amount": 19.999, "reason": "late"}, order_total=100)
    assert out["amount"] == 20.0


def test_outbox_records_and_reads_back(tmp_path):
    outbox = Outbox(str(tmp_path / "out" / "log.jsonl"))
    assert outbox.read_all() == []
    outbox.record("reply", "t1", text="hello")
    outbox.record("refund", "t1", amount=10.0)
    entries = outbox.read_all()
    assert [e["kind"] for e in entries] == ["reply", "refund"]
    assert entries[1]["amount"] == 10.0


def test_store_lists_newest_first(tmp_path):
    store = TicketStore(str(tmp_path / "tickets.db"))
    store.add("a", "first")
    store.add("b", "second")
    assert store.ids() == ["b", "a"]
