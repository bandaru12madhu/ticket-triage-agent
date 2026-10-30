# Support Ticket Triage Agent

A FastAPI service that reads customer support tickets, sorts them, drafts a reply from a knowledge base, and stops for human approval before anything risky happens (refunds and escalations).

This is project 4 in my agent portfolio. The store in the sample data (Brightcart) and its policies are made up.

## What happens to a ticket

```
POST /tickets
     |
 classify -> retrieve -> propose_action -> draft_reply
                                               |
                          action is "none"? ---+--- refund or escalate?
                                |                          |
                            auto_send                  approval   (waits for a person)
                                |                          |
                               END                      finalize
                                                           |
                                                          END
```

1. **classify** picks a category (billing, technical, account, shipping, other), a priority and a one line summary.
2. **retrieve** finds the matching sections of the knowledge base in `kb/`.
3. **propose_action** decides between no action, a refund, or an escalation.
4. **draft_reply** writes the reply using only the policy text it was given.
5. If the action is a refund or an escalation, the graph pauses at **approval**. A person reviews the ticket through the API and either approves it (optionally editing the reply) or rejects it.

Plain tickets, like a password question, get their reply sent automatically.

## Safety rules

- Refunds and escalations never run without a person approving them. Nothing is written to the outbox before approval.
- This rule is plain code, not something the model decides. A prompt cannot talk the agent out of it.
- A refund can never be larger than the order total. A refund with no usable amount becomes an escalation.
- The ticket text is treated as data in every prompt.
- A rejected ticket is held for a human agent and nothing is executed.

## Outbox

Sending email, paying refunds and creating escalations are simulated. Each one is written as a line in `data/outbox.jsonl`, for example:

```
{"time": "...", "kind": "refund", "ticket_id": "...", "amount": 40.0, "reason": "..."}
```

To use this for real, replace the `Outbox.record` calls in `app/graph.py` with calls to an email service, a payment API and a ticketing system.

## API

| Endpoint | Method | What it does |
|---|---|---|
| `/tickets` | POST | Submit a ticket. Returns its status and, if it is waiting, the proposed action and draft reply |
| `/tickets` | GET | List tickets. Add `?status=waiting_for_approval` to see the review queue |
| `/tickets/{id}` | GET | Look at one ticket |
| `/tickets/{id}/review` | POST | Approve or reject: `{"approved": true, "note": "...", "edited_reply": "..."}` |
| `/health` | GET | Simple health check |

Statuses are `waiting_for_approval`, `auto_replied`, `resolved` and `rejected`.

Pending tickets survive a restart because the graph state is saved in SQLite (`data/checkpoints.db`).

## Project layout

```
ticket-triage/
  app/
    main.py         FastAPI app and endpoints
    graph.py        LangGraph flow, approval step, safety rules
    knowledge.py    keyword search over the markdown knowledge base
    models.py       request and output models
    outbox.py       simulated email, refund and escalation log
    store.py        list of ticket ids in SQLite
    llm.py          OpenAI or Anthropic model from .env
  kb/               knowledge base files
  samples/          example tickets
  tests/
  Dockerfile
  docker-compose.yml
  requirements.txt
```

## Run it

```bash
python -m venv .venv
source .venv/bin/activate        # on Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

cp .env.example .env             # on Windows: copy .env.example .env
# add your key and choose LLM_PROVIDER

uvicorn app.main:app --reload
```

Open http://localhost:8000/docs. It has a built in page where you can try every endpoint. Paste one of the files from `samples/` into `POST /tickets`, then use `GET /tickets` and `POST /tickets/{id}/review` to approve it.

With curl:

```bash
curl -X POST http://localhost:8000/tickets -H "Content-Type: application/json" -d @samples/refund_request.json
curl "http://localhost:8000/tickets?status=waiting_for_approval"
curl -X POST http://localhost:8000/tickets/TICKET_ID/review -H "Content-Type: application/json" -d '{"approved": true, "note": "photo checked"}'
```

### Docker

```bash
cp .env.example .env
docker compose up --build
```

The `data` folder is mounted into the container so tickets and the outbox are kept between runs.

## Tests

```bash
pytest
```

No API key needed. The tests use a scripted stand-in for the model and cover the knowledge base search, the safety rules, the approval pause, approving, editing and rejecting, and the API endpoints.

## Ideas for next steps

- Replace keyword search with embeddings and a vector database (see project 2)
- Add a login and roles so only reviewers can approve
- Send real emails and connect a real ticketing tool
- Measure triage accuracy with a labeled set of tickets (project 5)
