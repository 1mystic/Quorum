from datetime import datetime
from sqlalchemy import select, func

from app.models import InsightRun
from app.repository.base import TenantScopedRepository


class InsightRunRepository(TenantScopedRepository):
    """
    Card C.10. The only repository the read surface (`GET /api/t/{slug}/
    insights/...`) touches: it reads a materialized row and serializes
    `payload` unchanged, never computes.

    Rows are append-only (`docs/STATS_API.md` section 2): `record_run` never
    updates a payload in place. A recomputation inserts a new row and points
    the row it replaces at it via `superseded_by`, which is what makes
    `GET .../history` a real trend of recomputations rather than a lossy
    overwrite.
    """

    async def record_run(
        self, *, pack: str, service: str, scope_key: str, params_hash: str,
        window_start: datetime, window_end: datetime, payload: dict, n: int,
        n_censored: int, insufficient: bool, worst_status: str, blocking: bool,
        contract_version: int, duration_ms: int, stale_after: datetime,
    ) -> InsightRun:
        previous = await self.latest(service, scope_key)

        run = InsightRun(
            tenant_id=self.tenant_id, pack=pack, service=service, scope_key=scope_key,
            params_hash=params_hash, window_start=window_start, window_end=window_end,
            payload=payload, n=n, n_censored=n_censored, insufficient=insufficient,
            worst_status=worst_status, blocking=blocking, contract_version=contract_version,
            duration_ms=duration_ms, stale_after=stale_after,
        )
        self.db.add(run)
        await self.db.flush()

        if previous is not None and previous.id != run.id:
            previous.superseded_by = run.id

        return run

    async def latest(self, service: str, scope_key: str = "") -> InsightRun | None:
        result = await self.db.execute(
            self.scope(select(InsightRun), InsightRun)
            .where(
                InsightRun.service == service,
                InsightRun.scope_key == scope_key,
                InsightRun.superseded_by.is_(None),
            )
            .order_by(InsightRun.computed_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def latest_by_params(self, service: str, scope_key: str, params_hash: str) -> InsightRun | None:
        result = await self.db.execute(
            self.scope(select(InsightRun), InsightRun)
            .where(
                InsightRun.service == service,
                InsightRun.scope_key == scope_key,
                InsightRun.params_hash == params_hash,
            )
            .order_by(InsightRun.computed_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def latest_for_pack(self, pack: str) -> list[InsightRun]:
        result = await self.db.execute(
            self.scope(select(InsightRun), InsightRun)
            .where(InsightRun.pack == pack, InsightRun.superseded_by.is_(None))
            .order_by(InsightRun.service, InsightRun.scope_key)
        )
        return list(result.scalars().all())

    async def history(self, service: str, scope_key: str = "") -> list[InsightRun]:
        result = await self.db.execute(
            self.scope(select(InsightRun), InsightRun)
            .where(InsightRun.service == service, InsightRun.scope_key == scope_key)
            .order_by(InsightRun.computed_at.asc())
        )
        return list(result.scalars().all())

    async def health(self) -> dict:
        result = await self.db.execute(
            self.scope(select(InsightRun), InsightRun)
            .where(InsightRun.superseded_by.is_(None))
        )
        rows = list(result.scalars().all())
        by_status = {"PASS": 0, "WARN": 0, "FAIL": 0}
        for row in rows:
            by_status[row.worst_status] = by_status.get(row.worst_status, 0) + 1
        return {
            "total": len(rows),
            "by_status": by_status,
            "stale": 0,   # set by the caller, which knows "now"
            "insufficient": sum(1 for row in rows if row.insufficient),
            "insufficient_services": [
                {"service": row.service, "scope_key": row.scope_key, "n": row.n}
                for row in rows if row.insufficient
            ],
            "last_computed_at": max((row.computed_at for row in rows), default=None),
        }
