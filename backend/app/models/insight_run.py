"""
Card C.10. `docs/STATS_API.md` section 2's `insight_runs` table, verbatim.

The only table the read surface serves from. Nothing under `/api/t/{slug}/
insights/...` ever computes a statistic; it reads a row here and serializes
`payload` unchanged. `payload` is the *entire* `Evidence.to_wire()` envelope,
written whole by the worker and never partially updated - there is no
`UPDATE ... SET payload = jsonb_set(...)` anywhere in this codebase, and a
review that finds one rejects it.

Rows are append-only: a recomputation inserts a new row and points the old
one's `superseded_by` at it, which is what lets the API say "this figure was
computed differently in June" instead of silently comparing two numbers that
are not the same thing (`params_hash` is the thing that changed).
"""
from datetime import datetime
from sqlalchemy import ForeignKey, DateTime, Index, Boolean, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.core import Base, utcnow


class InsightRun(Base):
    __tablename__ = "insight_runs"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "service", "scope_key", "params_hash", "window_end",
            name="uq_insight_runs_identity",
        ),
        Index("ix_insight_runs_tenant_pack_computed", "tenant_id", "pack", "computed_at"),
        Index("ix_insight_runs_tenant_stale", "tenant_id", "stale_after"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"))
    pack: Mapped[str] = mapped_column(String())
    service: Mapped[str] = mapped_column(String())            # Evidence.method
    scope_key: Mapped[str] = mapped_column(String(), default="", server_default="")
    params_hash: Mapped[str] = mapped_column(String())        # Evidence.params_hash
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))   # == Evidence.as_of
    payload: Mapped[dict] = mapped_column(JSONB)               # the ENTIRE envelope, wire format
    n: Mapped[int] = mapped_column(Integer())
    n_censored: Mapped[int] = mapped_column(Integer(), default=0, server_default="0")
    insufficient: Mapped[bool] = mapped_column(Boolean(), default=False, server_default="false")
    worst_status: Mapped[str] = mapped_column(String())        # PASS | WARN | FAIL
    blocking: Mapped[bool] = mapped_column(Boolean(), default=False, server_default="false")
    contract_version: Mapped[int] = mapped_column(Integer(), default=1, server_default="1")
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                   default=utcnow, server_default=func.now())
    duration_ms: Mapped[int] = mapped_column(Integer(), default=0, server_default="0")
    stale_after: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    superseded_by: Mapped[int | None] = mapped_column(ForeignKey("insight_runs.id"))


__all__ = ["InsightRun"]
