from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Club, ClubStatus, Membership, MembershipRole, MembershipStatus, Student, User
from sqlalchemy import select, func
from sqlalchemy.orm import aliased, selectinload


class MembershipRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_membership(self, student_id: int, club_id: int, role: MembershipRole,
                                status: MembershipStatus) -> Membership:
        new_membership = Membership(
            student_id=student_id,
            club_id=club_id,
            role=role,
            status=status,
        )
        self.db.add(new_membership)
        await self.db.flush()
        return new_membership

    async def get(self, student_id: int, club_id: int) -> Membership | None:
        result = await self.db.execute(
            select(Membership).where(
                Membership.student_id == student_id, Membership.club_id == club_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, membership_id: int) -> Membership | None:
        result = await self.db.execute(select(Membership).where(Membership.id == membership_id))
        return result.scalar_one_or_none()

    async def is_leader(self, student_id: int, club_id: int) -> bool:
        result = await self.db.execute(
            select(Membership).where(
                Membership.student_id == student_id,
                Membership.club_id == club_id,
                Membership.role == MembershipRole.LEADER,
                Membership.status == MembershipStatus.APPROVED,
            )
        )
        return result.scalar_one_or_none() is not None

    async def list_by_student(self, student_id: int, role: MembershipRole | None = None,
                              membership_status: MembershipStatus | None = None,
                              club_status: ClubStatus | None = None) -> list[tuple[Membership, Club, int, str]]:
        conditions = [Membership.student_id == student_id]
        if role is not None:
            conditions.append(Membership.role == role)
        if membership_status is not None:
            conditions.append(Membership.status == membership_status)
        if club_status is not None:
            conditions.append(Club.status == club_status)

        approved = aliased(Membership)
        member_count = (
            select(func.count(approved.id))
            .where(approved.club_id == Club.id, approved.status == MembershipStatus.APPROVED)
            .scalar_subquery()
        )

        result = await self.db.execute(
            select(Membership, Club, member_count, User.full_name)
            .join(Club, Club.id == Membership.club_id)
            .join(Student, Student.id == Club.club_head)
            .join(User, User.id == Student.user_id)
            .options(selectinload(Club.links))
            .where(*conditions)
            .order_by(Membership.created_at.desc())
        )
        return result.all()

    async def get_pending_by_club(self, club_id: int) -> list[tuple[Membership, str]]:
        result = await self.db.execute(
            select(Membership, User.full_name)
            .join(Student, Membership.student_id == Student.id)
            .join(User, Student.user_id == User.id)
            .where(Membership.club_id == club_id, Membership.status == MembershipStatus.PENDING)
            .order_by(Membership.created_at.asc())
        )
        return result.all()

    async def get_members_by_club(self, club_id: int) -> list[tuple[Membership, str]]:
        result = await self.db.execute(
            select(Membership, User.full_name)
            .join(Student, Membership.student_id == Student.id)
            .join(User, Student.user_id == User.id)
            .where(Membership.club_id == club_id, Membership.status == MembershipStatus.APPROVED)
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
