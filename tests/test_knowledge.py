from app.knowledge import KnowledgeBase, tokenize
from tests.fakes import KB_DIR


def test_tokenize_drops_short_and_common_words():
    words = tokenize("How do I get a refund for the broken item?")
    assert "refund" in words
    assert "broken" in words
    assert "the" not in words
    assert "how" not in words


def test_search_finds_refund_policy():
    kb = KnowledgeBase(KB_DIR)
    results = kb.search("my order arrived damaged, can I get a refund?")
    assert results
    assert results[0]["source"] == "refund_policy.md"


def test_search_finds_password_help():
    kb = KnowledgeBase(KB_DIR)
    results = kb.search("I forgot my password and the reset email is missing")
    assert results[0]["source"] == "account_help.md"


def test_search_returns_nothing_for_unrelated_text():
    kb = KnowledgeBase(KB_DIR)
    assert kb.search("zzzz qqqq xxxx") == []


def test_search_respects_top_k():
    kb = KnowledgeBase(KB_DIR)
    assert len(kb.search("refund order shipping account", top_k=2)) <= 2
