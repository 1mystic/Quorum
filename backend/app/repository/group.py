from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Group, GroupLink, GroupType, GroupStatus, Membership, MembershipStatus, Member, User, Tenant
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload


class GroupRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_group(self, tenant_id: int, group_head: int, name: str, description: str,
                          category: str, type: GroupType, status: GroupStatus, image_url: str | None) -> Group:
        new_group = Group(
            tenant_id=tenant_id,
            group_head=group_head,
            name=name,
            description=description,
            category=category,
            type=type,
            status=status,
            image_url=image_url,
        )
        self.db.add(new_group)
        await self.db.flush()
        return new_group

    async def add_link(self, group_id: int, label: str, url: str) -> GroupLink:
        new_link = GroupLink(group_id=group_id, label=label, url=url)
        self.db.add(new_link)
        return new_link

    async def get_by_id(self, group_id: int) -> Group | None:
        result = await self.db.execute(
            select(Group)
            .where(Group.id == group_id)
            .options(selectinload(Group.links), selectinload(Group.head).selectinload(Member.user))
        )
        return result.scalar_one_or_none()

    async def list_by_tenant(self, tenant_id: int, status: GroupStatus | None = None,
                              search: str | None = None, category: str | None = None,
                              type: GroupType | None = None) -> list[tuple[Group, int, str]]:
        conditions = [Group.tenant_id == tenant_id]
        if status is not None:
            conditions.append(Group.status == status)
        if type is not None:
            conditions.append(Group.type == type)
        if category:
            conditions.append(Group.category.ilike(category))
        if search:
            pattern = f"%{search}%"
            conditions.append(
                or_(Group.name.ilike(pattern), Group.description.ilike(pattern), Group.category.ilike(pattern))
            )

        result = await self.db.execute(
            select(Group, func.count(Membership.id), User.full_name)
            .outerjoin(
                Membership,
                (Membership.group_id == Group.id) & (Membership.status == MembershipStatus.APPROVED),
            )
            .join(Member, Member.id == Group.group_head)
            .join(User, User.id == Member.user_id)
            .options(selectinload(Group.links))
            .where(*conditions)
            .group_by(Group.id, User.full_name)
            .order_by(Group.created_at.desc())
        )
        return result.all()

    async def list_trending(self, limit: int = 8) -> list[tuple[Group, int, str, str]]:
        """Public, cross-tenant - active groups ranked by approved member
        count, for the unauthenticated marketing landing page."""
        result = await self.db.execute(
            select(Group, func.count(Membership.id), Tenant.name, Tenant.slug)
            .join(Tenant, Tenant.id == Group.tenant_id)
            .outerjoin(
                Membership,
                (Membership.group_id == Group.id) & (Membership.status == MembershipStatus.APPROVED),
            )
            .where(Group.status == GroupStatus.ACTIVE)
            .group_by(Group.id, Tenant.name, Tenant.slug)
            .order_by(func.count(Membership.id).desc(), Group.created_at.desc())
            .limit(limit)
        )
        return result.all()

    async def count_members(self, group_id: int) -> int:
        result = await self.db.execute(
            select(func.count(Membership.id)).where(
                Membership.group_id == group_id, Membership.status == MembershipStatus.APPROVED
            )
        )
        return result.scalar_one()

    async def update_group(self, group: Group, description: str | None, category: str | None,
                          image_url: str | None) -> Group:
        if description is not None:
            group.description = description
        if category is not None:
            group.category = category
        if image_url is not None:
            group.image_url = image_url
        return group

    async def replace_links(self, group_id: int, links: list) -> None:
        existing = await self.db.execute(select(GroupLink).where(GroupLink.group_id == group_id))
        for link in existing.scalars().all():
            await self.db.delete(link)
        await self.db.flush()
        for link in links:
            self.db.add(GroupLink(group_id=group_id, label=link.label, url=link.url))

    async def set_status(self, group: Group, status: GroupStatus) -> Group:
        group.status = status
        return group
