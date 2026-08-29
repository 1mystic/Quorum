from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Group, GroupStatus, Membership, MembershipRole, MembershipStatus, Member, User
from sqlalchemy import select, func
from sqlalchemy.orm import aliased, selectinload


class MembershipRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_membership(self, member_id: int, group_id: int, role: MembershipRole,
                                status: MembershipStatus) -> Membership:
        # tenant_id derived from the parent group, never from the caller.
        tenant_id = (await self.db.execute(
            select(Group.tenant_id).where(Group.id == group_id)
        )).scalar_one()
        new_membership = Membership(
            tenant_id=tenant_id,
            member_id=member_id,
            group_id=group_id,
            role=role,
            status=status,
        )
        self.db.add(new_membership)
        await self.db.flush()
        return new_membership

    async def get(self, member_id: int, group_id: int) -> Membership | None:
        result = await self.db.execute(
            select(Membership).where(
                Membership.member_id == member_id, Membership.group_id == group_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, membership_id: int) -> Membership | None:
        result = await self.db.execute(select(Membership).where(Membership.id == membership_id))
        return result.scalar_one_or_none()

    async def is_leader(self, member_id: int, group_id: int) -> bool:
        result = await self.db.execute(
            select(Membership).where(
                Membership.member_id == member_id,
                Membership.group_id == group_id,
                Membership.role == MembershipRole.LEADER,
                Membership.status == MembershipStatus.APPROVED,
            )
        )
        return result.scalar_one_or_none() is not None

    async def list_by_member(self, member_id: int, role: MembershipRole | None = None,
                              membership_status: MembershipStatus | None = None,
                              group_status: GroupStatus | None = None) -> list[tuple[Membership, Group, int, str]]:
        conditions = [Membership.member_id == member_id]
        if role is not None:
            conditions.append(Membership.role == role)
        if membership_status is not None:
            conditions.append(Membership.status == membership_status)
        if group_status is not None:
            conditions.append(Group.status == group_status)

        approved = aliased(Membership)
        member_count = (
            select(func.count(approved.id))
            .where(approved.group_id == Group.id, approved.status == MembershipStatus.APPROVED)
            .scalar_subquery()
        )

        result = await self.db.execute(
            select(Membership, Group, member_count, User.full_name)
            .join(Group, Group.id == Membership.group_id)
            .join(Member, Member.id == Group.group_head)
            .join(User, User.id == Member.user_id)
            .options(selectinload(Group.links))
            .where(*conditions)
            .order_by(Membership.created_at.desc())
        )
        return result.all()

    async def get_pending_by_group(self, group_id: int) -> list[tuple[Membership, str]]:
        result = await self.db.execute(
            select(Membership, User.full_name)
            .join(Member, Membership.member_id == Member.id)
            .join(User, Member.user_id == User.id)
            .where(Membership.group_id == group_id, Membership.status == MembershipStatus.PENDING)
            .order_by(Membership.created_at.asc())
        )
        return result.all()

    async def get_members_by_group(self, group_id: int) -> list[tuple[Membership, str]]:
        result = await self.db.execute(
            select(Membership, User.full_name)
            .join(Member, Membership.member_id == Member.id)
            .join(User, Member.user_id == User.id)
            .where(Membership.group_id == group_id, Membership.status == MembershipStatus.APPROVED)
            .order_by(Membership.created_at.asc())
        )
        return result.all()

    async def set_status(self, membership: Membership, status: MembershipStatus) -> Membership:
        membership.status = status
        return membership

    async def delete(self, membership: Membership) -> None:
        """
        Remove a membership outright rather than setting a status for it.

        There is no "REMOVED" member state - once gone, a former member is
        indistinguishable from someone who never joined, and can request to
        join again like anyone else.
        """
        await self.db.delete(membership)
        await self.db.flush()
