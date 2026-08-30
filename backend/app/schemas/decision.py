from datetime import datetime
from pydantic import BaseModel, Field

from app.models import DecisionKind, BallotStyle


class CreateDecisionOptionRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=200)
    cost_minor: int | None = Field(None, ge=0)
    tags: list[str] = Field(default_factory=list)


class CreateDecisionRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    kind: DecisionKind
    declared_rule: str = Field(..., min_length=1, max_length=32)
    ballot_style: BallotStyle
    seats: int = Field(1, ge=1)
    quorum_rule: str | None = Field(None, max_length=32)
    budget_minor: int | None = Field(None, ge=0)
    group_id: int | None = None
    options: list[CreateDecisionOptionRequest] = Field(default_factory=list, min_length=1)


class DecisionOptionItem(BaseModel):
    id: int
    label: str
    cost_minor: int | None
    tags: list[str]


class DecisionItem(BaseModel):
    id: int
    title: str
    description: str | None
    kind: DecisionKind
    declared_rule: str
    ballot_style: BallotStyle
    seats: int
    quorum_rule: str | None
    budget_minor: int | None
    opened_at: datetime
    closed_at: datetime | None
    options: list[DecisionOptionItem]


class CastBallotRequest(BaseModel):
    # Tuple of tiers for a ranked ballot: a list of lists of option ids.
    # An option absent from every tier is unranked.
    ranking: list[list[int]] = Field(default_factory=list)
    approvals: list[int] = Field(default_factory=list)
    scores: dict[int, int] = Field(default_factory=dict)
    allocation: dict[int, int] = Field(default_factory=dict)
    channel: str | None = Field(None, max_length=32)


class BallotItem(BaseModel):
    id: int
    decision_id: int
    voter_id: int
    cast_at: datetime
    ranking: list[list[int]]
    approvals: list[int]
    scores: dict[int, int]
    allocation: dict[int, int]


class DecisionActionResponse(BaseModel):
    id: int
    message: str
