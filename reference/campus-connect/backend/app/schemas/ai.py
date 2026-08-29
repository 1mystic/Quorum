from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str


class AgentChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)
    # What the student typed into the finder box. Used to derive durable
    # interest memory, and as the fallback query if the model is unreachable.
    interest_text: str = ""


class AgentChatResponse(BaseModel):
    reply: str
    kind: str
    items: list = Field(default_factory=list)
    # The model was unreachable, so the deterministic recommender answered.
    degraded: bool
    # The live database was unreachable or unseeded, so the answer is grounded
    # in the sample campus rather than this college's real data.
    offline: bool = False
    tools_used: list[str] = Field(default_factory=list)
    iterations: int = 0
    budget_exhausted: bool = False
