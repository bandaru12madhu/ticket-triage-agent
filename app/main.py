import os
import sqlite3
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from langgraph.types import Command

from app.knowledge import KnowledgeBase
from app.llm import get_llm
from app.models import ReviewIn, TicketIn
from app.outbox import Outbox
from app.store import TicketStore


def describe(graph, ticket_id):
    """Build the API view of a ticket from its saved graph state."""
    config = {"configurable": {"thread_id": ticket_id}}
    snapshot = graph.get_state(config)
    values = snapshot.values
    if not values:
        return None

    classification = values.get("classification", {})
    return {
        "ticket_id": ticket_id,
        "status": "waiting_for_approval" if snapshot.next else values.get("status", "unknown"),
        "subject": values["ticket"]["subject"],
        "category": classification.get("category"),
        "priority": classification.get("priority"),
        "summary": classification.get("summary"),
        "proposed_action": values.get("action"),
        "draft_reply": values.get("reply"),
        "outcome": values.get("outcome"),
    }


def build_default_graph(data_dir):
    from langgraph.checkpoint.sqlite import SqliteSaver

    from app.graph import build_graph

    conn = sqlite3.connect(str(Path(data_dir) / "checkpoints.db"), check_same_thread=False)
    return build_graph(
        get_llm(),
        KnowledgeBase(os.getenv("KB_DIR", "kb")),
        Outbox(str(Path(data_dir) / "outbox.jsonl")),
        SqliteSaver(conn),
    )


def create_app(graph=None, store=None, data_dir=None):
    data_dir = data_dir or os.getenv("DATA_DIR", "data")

    app = FastAPI(title="Support Ticket Triage", version="1.0.0")
    holder = {"graph": graph, "store": store}

    def get_graph():
        # built on first use so importing the module does not need an API key
        if holder["graph"] is None:
            Path(data_dir).mkdir(parents=True, exist_ok=True)
            holder["graph"] = build_default_graph(data_dir)
        return holder["graph"]

    def get_store():
        if holder["store"] is None:
            Path(data_dir).mkdir(parents=True, exist_ok=True)
            holder["store"] = TicketStore(str(Path(data_dir) / "tickets.db"))
        return holder["store"]

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/tickets", status_code=201)
    def submit_ticket(ticket: TicketIn):
        ticket_id = uuid.uuid4().hex[:10]
        config = {"configurable": {"thread_id": ticket_id}}
        data = ticket.model_dump()
        data["id"] = ticket_id
        try:
            get_graph().invoke({"ticket": data}, config)
        except Exception as err:
            raise HTTPException(502, "The agent failed to process the ticket: " + str(err))
        get_store().add(ticket_id, ticket.subject)
        return describe(get_graph(), ticket_id)

    @app.get("/tickets")
    def list_tickets(status: str | None = None):
        tickets = []
        for ticket_id in get_store().ids():
            info = describe(get_graph(), ticket_id)
            if info and (status is None or info["status"] == status):
                tickets.append(info)
        return tickets

    @app.get("/tickets/{ticket_id}")
    def get_ticket(ticket_id: str):
        info = describe(get_graph(), ticket_id)
        if info is None:
            raise HTTPException(404, "Ticket not found")
        return info

    @app.post("/tickets/{ticket_id}/review")
    def review_ticket(ticket_id: str, review: ReviewIn):
        info = describe(get_graph(), ticket_id)
        if info is None:
            raise HTTPException(404, "Ticket not found")
        if info["status"] != "waiting_for_approval":
            raise HTTPException(409, "This ticket is not waiting for approval")

        config = {"configurable": {"thread_id": ticket_id}}
        get_graph().invoke(Command(resume=review.model_dump()), config)
        return describe(get_graph(), ticket_id)

    return app


app = create_app()
