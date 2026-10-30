from pathlib import Path

from langchain_core.messages import AIMessage

from app.models import Classification, ProposedAction

KB_DIR = str(Path(__file__).resolve().parent.parent / "kb")


class Structured:
    def __init__(self, queue):
        self.queue = queue

    def invoke(self, messages):
        return self.queue.pop(0)


class ScriptedModel:
    """Stands in for a real chat model so the tests need no API key.
    Answers are handed out in the order the graph asks for them."""

    def __init__(self, classifications, actions, replies):
        self.queues = {
            Classification: list(classifications),
            ProposedAction: list(actions),
        }
        self.replies = list(replies)

    def with_structured_output(self, schema):
        return Structured(self.queues[schema])

    def invoke(self, messages):
        return AIMessage(content=self.replies.pop(0))


def classification(category="billing", priority="medium", summary="Customer needs help"):
    return Classification(category=category, priority=priority, summary=summary)


def action(kind="none", amount=None, reason="No action needed"):
    return ProposedAction(type=kind, amount=amount, reason=reason)
