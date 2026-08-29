from sqlalchemy.ext.asyncio import AsyncSession
from app.models import College
from sqlalchemy import select, literal, func, exists


class CollegeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        
    async def email_to_college(self, email: str) -> College | None:
        domain = email.split("@")[-1]
        result = await self.db.execute(
            select(College).where(
                (College.email_suffix == domain)| literal(domain).like("%." + College.email_suffix)
            )
        )
        return result.scalar_one_or_none()
    
    async def id_to_slug(self, id: int) -> str:
        result = await self.db.execute(select(College.slug).where(College.id==id))
        return result.scalar()
    
    async def create_college(self, name: str, email_suffix: str, slug: str, description: str):
        new_college = College(
            name=name,
            email_suffix=email_suffix,
            slug=slug,
            description=description
        )
        self.db.add(new_college)
        await self.db.flush()
        return new_college
    
    async def slug_count(self, slug: str) -> int:
        result = await self.db.execute(
            select(func.count(College.id)).where(College.slug.like(slug + "%"))
        )
        return result.scalar_one()
    
    async def is_college_exist(self, email_suffix: str) -> bool:
        result = await self.db.execute(select(exists().where(College.email_suffix==email_suffix)))
        return result.scalar()