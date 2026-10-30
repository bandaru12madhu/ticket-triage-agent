from typing import Literal

from pydantic import BaseModel, Field


class TicketIn(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=5000)
    customer_email: str | None = None
    order_total: float | None = Field(default=None, gt=0)


class ReviewIn(BaseModel):
    approved: bool
    note: str = ""
    edited_reply: str | None = None


class Classification(BaseModel):
    category: Literal["billing", "technical", "account", "shipping", "other"]
    priority: Literal["low", "medium", "high", "urgent"]
    summary: str = Field(description="One sentence describing what the customer wants")


class ProposedAction(BaseModel):
    type: Literal["none", "refund", "escalate"]
    amount: float | None = Field(default=None, description="Refund amount, only for refunds")
    reason: str = Field(description="Why this action is needed, in one sentence")
