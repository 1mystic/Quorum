"""
Card C.15 (decision half). docs/GLOSSARY.md's new entities table: Poll,
Ballot, Allocation -> the `decision` stream (docs/DATA_SPINE.md section 6).

Three tables, matching the three atoms `app/stats/streams/decision.py`
already declares:

- `Decision` (the "Poll") is the declaration, frozen at open time. Rule D1 is
  enforced here at the schema level, not just at the dataclass level:
  `declared_rule` is `nullable=False`, so a decision cannot exist without a
  declared rule any more than `DecisionSpec.__post_init__` allows one. The
  platform may disclose other rules' winners afterwards, but the rule that
  decides was on record before the first ballot.
- `DecisionOption` is one thing that can be voted for or funded. `cost_minor`
  is set for participatory budgeting (`kind == BUDGET_ALLOCATION`) and null
  otherwise.
- `Ballot` is one cast ballot. Its shape flexes with `Decision.ballot_style`:
  `ranking` for ranked, `approvals` for approval, `scores` for score,
  `allocation` for the participatory-budgeting shape (option -> minor units,
  the "Allocation" half of the glossary's three-entity list is this field on
  a budget_allocation ballot, not a fourth table, since the spine's own
  `Ballot` atom carries it the same way).

Nothing here counts a vote, finds a Condorcet winner or runs Method of Equal
Shares. That is `app/stats/voting.py`/`budgeting.py`'s job, downstream and
pure, once the adapter turns these rows into `Ballot`/`DecisionOption`/
`DecisionSpec` atoms.
"""
import enum
from datetime import datetime

from sqlalchemy import ForeignKey, Enum, DateTime, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core import Base, utcnow


class DecisionKind(str, enum.Enum):
    POLL = "poll"
    ELECTION = "election"
    BUDGET_ALLOCATION = "budget_allocation"
    REFERENDUM = "referendum"


class BallotStyle(str, enum.Enum):
    RANKED = "ranked"
    APPROVAL = "approval"
    SCORE = "score"
    SINGLE = "single"
    ALLOCATION = "allocation"


# Rule D1's vocabulary: the same six values `DecisionSpec.declared_rule`'s
# docstring names. Validated at the service layer, the same discipline
# `RequestService._validate_vocabulary` uses for category/priority, so a
# seventh rule does not need a migration.
DECLARED_RULES = ("schulze", "stv", "approval", "borda", "mes", "greedy")


class Decision(Base):
    """The "Poll": a decision's declaration, frozen at `opened_at`."""
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    group_id: Mapped[int | None] = mapped_column(ForeignKey("groups.id"))
    title: Mapped[str] = mapped_column()
    description: Mapped[str | None] = mapped_column()
    kind: Mapped[DecisionKind] = mapped_column(Enum(DecisionKind))
    # Rule D1, enforced at the schema: cannot be null, cannot be added later.
    declared_rule: Mapped[str] = mapped_column(nullable=False)
    seats: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    quorum_rule: Mapped[str | None] = mapped_column()
    budget_minor: Mapped[int | None] = mapped_column()
    ballot_style: Mapped[BallotStyle] = mapped_column(Enum(BallotStyle))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                default=utcnow, server_default=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # RosterSnapshot frozen at opened_at (spine section 8): a list of
    # {"strata": {...}, "count": n} rows, never recomputed after the fact, so
    # a later move-in cannot change a past turnout figure.
    eligible_strata: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow, server_default=func.now())

    options: Mapped[list["DecisionOption"]] = relationship(
        back_populates="decision", cascade="all, delete-orphan"
    )
    ballots: Mapped[list["Ballot"]] = relationship(
        back_populates="decision", cascade="all, delete-orphan"
    )


class DecisionOption(Base):
    __tablename__ = "decision_options"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id"))
    label: Mapped[str] = mapped_column()
    cost_minor: Mapped[int | None] = mapped_column()   # budget_allocation only
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, server_default="{}")
    proposer_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow, server_default=func.now())

    decision: Mapped["Decision"] = relationship(back_populates="options")
    proposer: Mapped["Member | None"] = relationship(foreign_keys=[proposer_id])


class Ballot(Base):
    """
    One cast ballot. `ranking`/`approvals`/`scores`/`allocation` all reference
    `DecisionOption.id`; the adapter turns these into the atom's
    `option_ref`-keyed shapes.

    One ballot per voter per decision: a second submission replaces the first
    at the service layer rather than accumulating silently, matching how a
    real poll works. `voter_id` is a member, kept out of any k-anonymised
    breakdown at the service layer (rule D2); a secret-ballot vertical would
    drop it before the atom leaves the adapter, which is the adapter's call to
    make, not this table's.
    """
    __tablename__ = "ballots"
    __table_args__ = (
        UniqueConstraint("decision_id", "voter_id", name="uq_ballot_decision_voter"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    decision_id: Mapped[int] = mapped_column(ForeignKey("decisions.id"))
    voter_id: Mapped[int] = mapped_column(ForeignKey("members.id"))
    cast_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                              default=utcnow, server_default=func.now())
    # Tuple of tiers for a ranked ballot: [[option_id, ...], [option_id, ...]].
    ranking: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    approvals: Mapped[list[int]] = mapped_column(ARRAY(Integer), default=list, server_default="{}")
    # {option_id (str): score} and {option_id (str): minor units}. JSON object
    # keys are always strings; the adapter re-keys them to int option_ref.
    scores: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    allocation: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    channel: Mapped[str | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                 default=utcnow, server_default=func.now())

    decision: Mapped["Decision"] = relationship(back_populates="ballots")
    voter: Mapped["Member"] = relationship(foreign_keys=[voter_id])
