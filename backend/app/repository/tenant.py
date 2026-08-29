from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Tenant
from sqlalchemy import select, func, exists


class TenantRepository:
    """
    Unscoped by design: a tenant looks itself up by slug before any tenant_id
    exists in the request. Every other repository in this codebase should
    inherit TenantScopedRepository instead - see app/repository/base.py.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_slug(self, slug: str) -> Tenant | None:
        result = await self.db.execute(select(Tenant).where(Tenant.slug == slug))
        return result.scalar_one_or_none()

    async def get_by_id(self, id: int) -> Tenant | None:
        result = await self.db.execute(select(Tenant).where(Tenant.id == id))
        return result.scalar_one_or_none()

    async def id_to_slug(self, id: int) -> str:
        result = await self.db.execute(select(Tenant.slug).where(Tenant.id == id))
        return result.scalar()

    async def create_tenant(self, name: str, slug: str, vertical: str, description: str):
        new_tenant = Tenant(
            name=name,
            slug=slug,
            vertical=vertical,
            description=description,
        )
        self.db.add(new_tenant)
        await self.db.flush()
        return new_tenant

    async def slug_count(self, slug: str) -> int:
        result = await self.db.execute(
            select(func.count(Tenant.id)).where(Tenant.slug.like(slug + "%"))
        )
        return result.scalar_one()

    async def is_tenant_exist(self, slug: str) -> bool:
        result = await self.db.execute(select(exists().where(Tenant.slug == slug)))
        return result.scalar()
