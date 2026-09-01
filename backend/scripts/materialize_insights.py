"""
The worker entrypoint `app/services/insight_materializer.py` names in its own
docstring: walks every tenant and materializes its Insight Packs, matching
`PLAN.md`'s web/worker split (the light `web` tier only ever reads cached
`insight_runs` rows; this process is the thing that actually calls into
`app/stats/...` against live data).

    python scripts/materialize_insights.py            # loop forever
    python scripts/materialize_insights.py --once      # one pass, then exit

`MATERIALIZE_INTERVAL_SECONDS` controls the loop period (default one hour).
`docs/STATS_API.md`'s cadence table has nothing coarser than "nightly" and
several services at "hourly"; an hourly worker satisfies the loosest cadence
with room to spare and does not starve the tightest one for more than an
hour, which is the same trade-off a single cron entry would make.
"""
from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.tenancy import set_tenant_context
from app.models import Tenant
from app.services.insight_materializer import InsightMaterializer

INTERVAL_SECONDS = int(os.environ.get("MATERIALIZE_INTERVAL_SECONDS", "3600"))


async def materialize_once() -> None:
    async with SessionLocal() as list_db:
        tenants = (await list_db.execute(select(Tenant))).scalars().all()

    # One transaction per tenant, not one for the whole pass: `app.tenant_id`
    # is set with `is_local=true` (transaction-scoped), and `record_run`
    # defers its `superseded_by` UPDATE on the previous run to the next
    # flush. Sharing one transaction across tenants means that deferred
    # UPDATE can fire after the GUC has already moved to the next tenant,
    # which RLS then correctly refuses to match - a real bug this loop hit
    # once and is written this way specifically to avoid.
    for tenant in tenants:
        async with SessionLocal() as db:
            try:
                await set_tenant_context(db, tenant.id)
                materializer = InsightMaterializer(db, tenant)
                runs = await materializer.materialize_all()
                await db.commit()
            except Exception:
                await db.rollback()
                raise
            real = sum(1 for r in runs if not r.insufficient)
            print(f"materialize_insights: {tenant.slug}: {real}/{len(runs)} real reading(s)")


async def main() -> None:
    once = "--once" in sys.argv
    while True:
        try:
            await materialize_once()
        except Exception as exc:  # noqa: BLE001 - a worker loop must not die on one bad tenant
            print(f"materialize_insights: pass failed: {exc}", file=sys.stderr)
        if once:
            return
        await asyncio.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
