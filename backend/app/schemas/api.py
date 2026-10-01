from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str = Field(examples=["priya.sharma@example.com"])
    password: str = Field(examples=["demo1234"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000, examples=["My order A12345 hasn't arrived yet."])
    conversation_id: str | None = None


class ConfirmRequest(BaseModel):
    conversation_id: str
    confirm: bool


class TicketUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(Open|In Progress|Resolved|Closed)$")
    assigned_agent: str | None = None


class ReviewRequest(BaseModel):
    note: str = ""


class KBSearch(BaseModel):
    query: str = Field(min_length=2)
