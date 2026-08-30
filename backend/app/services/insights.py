"""
Card C.10. The read half of `docs/STATS_API.md`.

**The API never computes a statistic.** Every method here reads a cached
`insight_runs` row through `InsightRunRepository` and serializes what it
finds. When nothing has been computed yet it returns the calm, honest
"not enough data" shape rather than a 404 or a 422 (section 5: "not enough
data" is a 200, because if honesty returns an error code every client learns
that honest tools look broken).
"""
from datetime import datetime, timezone

from app.repository import InsightRunRepository
from app.stats import registry
from app.stats.contracts import Evidence, insufficient
from app.exceptions import InsightNotFoundError, PackDisabledError, StreamUnavailableError, TenantNotFoundError

# Streams that actually have rows behind them today. Everything else is a
# declared-empty stream per `app/verticals/adapters/base.py`'s TODOs
# (docs/DATA_SPINE.md's "four of six streams have no model" note in
# CONTEXT.md); a service that needs one of those streams is always
# `insufficient_data`, never fabricated. Kept here rather than in
# `app/verticals/` so this file, not the adapter, owns the "is this pack
# worth turning on yet" judgement call.
STREAMS_WITH_DATA = frozenset({"request_flow", "ledger"})


class InsightsService:
    def __init__(self, run_repo: InsightRunRepository, tenant_repo):
        self.run_repo = run_repo
        self.tenant_repo = tenant_repo

    async def packs(self, tenant_id: int) -> dict:
        tenant = await self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise TenantNotFoundError()
        enabled = set(tenant.enabled_packs or [])
        out = []
        for pack in registry.packs():
            streams_available = pack.required_streams & STREAMS_WITH_DATA
            available = streams_available == pack.required_streams
            specs = registry.for_pack(pack.id)
            rows = await self.run_repo.latest_for_pack(pack.id)
            by_service = {row.service: row for row in rows}
            ready = sum(1 for s in specs if s.implemented and s.id in by_service
                        and not by_service[s.id].insufficient)
            insuff = sum(1 for s in specs if s.implemented and s.id in by_service
                         and by_service[s.id].insufficient)
            blocked = sum(1 for s in specs if not s.implemented)
            last_computed = max((row.computed_at for row in rows), default=None)
            entry = {
                "id": pack.id, "name": pack.name,
                "enabled": pack.id in enabled,
                "available": available,
                "required_streams": sorted(pack.required_streams),
                "streams_available": sorted(streams_available),
                "cadence": pack.default_cadence,
                "services_ready": ready,
                "services_insufficient": insuff,
                "services_blocked": blocked,
                "last_computed_at": last_computed,
            }
            if not available:
                missing = sorted(pack.required_streams - streams_available)
                entry["reason"] = "needs the " + ", ".join(missing) + " stream" + (
                    "s" if len(missing) > 1 else ""
                )
            out.append(entry)
        return {"vertical": tenant.vertical, "packs": out}

    async def pack_insights(self, tenant_id: int, pack_id: str) -> list[dict]:
        await self._require_pack_enabled(tenant_id, pack_id)
        rows = await self.run_repo.latest_for_pack(pack_id)
        return [self._envelope_response(row) for row in rows]

    async def one_insight(self, tenant_id: int, pack_id: str, service_id: str,
                           scope: str = "") -> dict:
        await self._require_pack_enabled(tenant_id, pack_id)
        try:
            spec = registry.get(service_id)
        except KeyError:
            raise InsightNotFoundError()
        if spec.pack != pack_id:
            raise InsightNotFoundError()

        row = await self.run_repo.latest(service_id, scope)
        if row is None:
            envelope = insufficient(
                service_id, n=0, as_of=datetime.now(timezone.utc),
                caveats=("First run has not landed yet.",),
            )
            return {
                "service": service_id, "pack": pack_id, "scope": scope,
                "evidence": envelope.to_wire(), "computed_at": None, "stale_after": None,
                "is_stale": False, "method_url": "/api/methods/" + service_id,
            }
        return self._envelope_response(row)

    async def history(self, tenant_id: int, service_id: str, scope: str = "") -> list[dict]:
        rows = await self.run_repo.history(service_id, scope)
        return [self._envelope_response(row) for row in rows]

    async def health(self, tenant_id: int) -> dict:
        return await self.run_repo.health()

    # ---- helpers ----------------------------------------------------------

    async def _require_pack_enabled(self, tenant_id: int, pack_id: str) -> None:
        tenant = await self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise TenantNotFoundError()
        if pack_id not in (tenant.enabled_packs or []):
            raise PackDisabledError(pack_id)

    @staticmethod
    def _envelope_response(row) -> dict:
        now = datetime.now(timezone.utc)
        stale_after = row.stale_after
        is_stale = stale_after is not None and now > (
            stale_after if stale_after.tzinfo else stale_after.replace(tzinfo=timezone.utc)
        )
        return {
            "service": row.service, "pack": row.pack, "scope": row.scope_key,
            "evidence": row.payload, "computed_at": row.computed_at,
            "stale_after": row.stale_after, "is_stale": is_stale,
            "method_url": "/api/methods/" + row.service,
        }
