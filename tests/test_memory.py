from app.memory import CustomerMemory, NoMemory, clean_email


def entry(ticket_id="t1", summary="Asked about shipping", action="none", status="auto_replied"):
    return {
        "ticket_id": ticket_id,
        "category": "shipping",
        "summary": summary,
        "action": action,
        "status": status,
    }


def test_clean_email_trims_and_lowercases():
    assert clean_email("  Sam@Example.COM ") == "sam@example.com"
    assert clean_email(None) == ""
    assert clean_email("") == ""


def test_recent_returns_newest_first(tmp_path):
    memory = CustomerMemory(str(tmp_path / "m.db"))
    memory.add("sam@example.com", entry("t1", "first"))
    memory.add("sam@example.com", entry("t2", "second"))
    memory.add("sam@example.com", entry("t3", "third"))

    items = memory.recent("sam@example.com")
    assert [i["ticket_id"] for i in items] == ["t3", "t2", "t1"]
    assert items[0]["summary"] == "third"
    assert "created_at" in items[0]


def test_recent_respects_limit(tmp_path):
    memory = CustomerMemory(str(tmp_path / "m.db"))
    for number in range(7):
        memory.add("sam@example.com", entry("t" + str(number)))
    assert len(memory.recent("sam@example.com", limit=3)) == 3


def test_email_match_ignores_case_and_spaces(tmp_path):
    memory = CustomerMemory(str(tmp_path / "m.db"))
    memory.add("Sam@Example.com", entry())
    assert len(memory.recent(" sam@example.COM ")) == 1


def test_customers_do_not_see_each_other(tmp_path):
    memory = CustomerMemory(str(tmp_path / "m.db"))
    memory.add("sam@example.com", entry("a"))
    memory.add("lee@example.com", entry("b"))
    assert [i["ticket_id"] for i in memory.recent("sam@example.com")] == ["a"]
    assert [i["ticket_id"] for i in memory.recent("lee@example.com")] == ["b"]


def test_no_email_means_nothing_is_stored(tmp_path):
    memory = CustomerMemory(str(tmp_path / "m.db"))
    memory.add(None, entry())
    memory.add("", entry())
    assert memory.recent(None) == []
    assert memory.recent("") == []


def test_forget_deletes_only_that_customer(tmp_path):
    memory = CustomerMemory(str(tmp_path / "m.db"))
    memory.add("sam@example.com", entry("a"))
    memory.add("sam@example.com", entry("b"))
    memory.add("lee@example.com", entry("c"))

    assert memory.forget("sam@example.com") == 2
    assert memory.recent("sam@example.com") == []
    assert len(memory.recent("lee@example.com")) == 1
    assert memory.forget("nobody@example.com") == 0


def test_memory_survives_reopening_the_database(tmp_path):
    path = str(tmp_path / "m.db")
    CustomerMemory(path).add("sam@example.com", entry("a"))
    assert len(CustomerMemory(path).recent("sam@example.com")) == 1


def test_no_memory_does_nothing():
    memory = NoMemory()
    memory.add("sam@example.com", entry())
    assert memory.recent("sam@example.com") == []
    assert memory.forget("sam@example.com") == 0
