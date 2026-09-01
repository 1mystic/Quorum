"""
Runs `seed_demo.main()` only if the `tenants` table is empty.

This is what the docker-compose backend entrypoint calls after migrations,
so a fresh `docker compose up` boots with the two demo tenants already
loaded but a restart, or a second `docker compose up` against a volume an
operator has since put real data into, does not reseed on top of it.

    python scripts/seed_if_empty.py
"""
import asyncio

from sqlalchemy import text

from app.core.database import SessionLocal

import seed_demo  # sibling module in scripts/


async def main() -> None:
    async with SessionLocal() as db:
        count = (await db.execute(text("SELECT count(*) FROM tenants"))).scalar()
    if count and count > 0:
        print(f"seed_if_empty: {count} tenant(s) already present, skipping the demo seed")
        return
    print("seed_if_empty: no tenants found, running the demo seed")
    await seed_demo.main()


if __name__ == "__main__":
    asyncio.run(main())
