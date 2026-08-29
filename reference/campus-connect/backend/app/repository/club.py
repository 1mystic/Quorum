from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Club, ClubLink, ClubType, ClubStatus, Membership, MembershipStatus, Student, User, College
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload


class ClubRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_club(self, college_id: int, club_head: int, name: str, description: str,
                          category: str, type: ClubType, status: ClubStatus, image_url: str | None) -> Club:
        new_club = Club(
            college_id=college_id,
            club_head=club_head,
            name=name,
            description=description,
            category=category,
            type=type,
            status=status,
            image_url=image_url,
        )
        self.db.add(new_club)
        await self.db.flush()
        return new_club

    async def add_link(self, club_id: int, label: str, url: str) -> ClubLink:
        new_link = ClubLink(club_id=club_id, label=label, url=url)
        self.db.add(new_link)
        return new_link

    async def get_by_id(self, club_id: int) -> Club | None:
        result = await self.db.execute(
            select(Club)
            .where(Club.id == club_id)
            .options(selectinload(Club.links), selectinload(Club.head).selectinload(Student.user))
        )
        return result.scalar_one_or_none()

    async def list_by_college(self, college_id: int, status: ClubStatus | None = None,
                              search: str | None = None, category: str | None = None,
                              type: ClubType | None = None) -> list[tuple[Club, int, str]]:
        conditions = [Club.college_id == college_id]
        if status is not None:
            conditions.append(Club.status == status)
        if type is not None:
            conditions.append(Club.type == type)
        if category:
            conditions.append(Club.category.ilike(category))
        if search:
            pattern = f"%{search}%"
            conditions.append(
                or_(Club.name.ilike(pattern), Club.description.ilike(pattern), Club.category.ilike(pattern))
            )

        result = await self.db.execute(
            select(Club, func.count(Membership.id), User.full_name)
            .outerjoin(
                Membership,
                (Membership.club_id == Club.id) & (Membership.status == MembershipStatus.APPROVED),
            )
            .join(Student, Student.id == Club.club_head)
            .join(User, User.id == Student.user_id)
            .options(selectinload(Club.links))
            .where(*conditions)
            .group_by(Club.id, User.full_name)
            .order_by(Club.created_at.desc())
        )
        return result.all()

    async def list_trending(self, limit: int = 8) -> list[tuple[Club, int, str, str]]:
        """Public, cross-college - active clubs ranked by approved member
        count, for the unauthenticated marketing landing page."""
        result = await self.db.execute(
            select(Club, func.count(Membership.id), College.name, College.slug)
            .join(College, College.id == Club.college_id)
            .outerjoin(
                Membership,
                (Membership.club_id == Club.id) & (Membership.status == MembershipStatus.APPROVED),
            )
            .where(Club.status == ClubStatus.ACTIVE)
            .group_by(Club.id, College.name, College.slug)
            .order_by(func.count(Membership.id).desc(), Club.created_at.desc())
            .limit(limit)
        )
        return result.all()

    async def count_members(self, club_id: int) -> int:
        result = await self.db.execute(
            select(func.count(Membership.id)).where(
                Membership.club_id == club_id, Membership.status == MembershipStatus.APPROVED
            )
        )
        return result.scalar_one()

    async def update_club(self, club: Club, description: str | None, category: str | None,
                          image_url: str | None) -> Club:
        if description is not None:
            club.description = description
        if category is not None:
            club.category = category
        if image_url is not None:
            club.image_url = image_url
        return club

    async def replace_links(self, club_id: int, links: list) -> None:
        existing = await self.db.execute(select(ClubLink).where(ClubLink.club_id == club_id))
        for link in existing.scalars().all():
            await self.db.delete(link)
        await self.db.flush()
        for link in links:
            self.db.add(ClubLink(club_id=club_id, label=link.label, url=link.url))

    async def set_status(self, club: Club, status: ClubStatus) -> Club:
        club.status = status
        return club
