from sqlalchemy.ext.asyncio import AsyncSession
from app.models import (
    Issue, IssueCategory, IssueStatus, Club, Membership, MembershipRole,
    MembershipStatus, Student, User
)
from sqlalchemy import select, func
from sqlalchemy.orm import aliased, selectinload
from datetime import datetime, timezone


class IssueRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_issue(self, student_id: int, club_id: int, event_id: int | None,
                           category: IssueCategory, title: str, description: str) -> Issue:
        new_issue = Issue(
            student_id=student_id,
            club_id=club_id,
            event_id=event_id,
            category=category,
            status=IssueStatus.OPEN,
            title=title,
            description=description,
        )
        self.db.add(new_issue)
        await self.db.flush()
        return new_issue

    async def get_by_id(self, issue_id: int) -> Issue | None:
        result = await self.db.execute(
            select(Issue)
            .where(Issue.id == issue_id)
            .options(selectinload(Issue.club))
        )
        return result.scalar_one_or_none()

    async def list_by_student(self, student_id: int, status: IssueStatus | None = None,
                              club_id: int | None = None, limit: int = 50,
                              offset: int = 0) -> list[tuple[Issue, str, str | None]]:
        conditions = [Issue.student_id == student_id]
        if status is not None:
            conditions.append(Issue.status == status)
        if club_id is not None:
            conditions.append(Issue.club_id == club_id)

        responder = aliased(Student)
        responder_user = aliased(User)

        result = await self.db.execute(
            select(Issue, Club.name, responder_user.full_name)
            .join(Club, Club.id == Issue.club_id)
            .outerjoin(responder, responder.id == Issue.responded_by)
            .outerjoin(responder_user, responder_user.id == responder.user_id)
            .where(*conditions)
            .order_by(Issue.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.all()

    async def list_for_leader(self, student_id: int, status: IssueStatus | None = None,
                              club_id: int | None = None, limit: int = 50,
                              offset: int = 0) -> list[tuple[Issue, str, str, str | None]]:
        conditions = [
            Membership.student_id == student_id,
            Membership.role == MembershipRole.LEADER,
            Membership.status == MembershipStatus.APPROVED,
        ]
        if status is not None:
            conditions.append(Issue.status == status)
        if club_id is not None:
            conditions.append(Issue.club_id == club_id)

        raiser = aliased(Student)
        raiser_user = aliased(User)
        responder = aliased(Student)
        responder_user = aliased(User)

        result = await self.db.execute(
            select(Issue, Club.name, raiser_user.full_name, responder_user.full_name)
            .join(Club, Club.id == Issue.club_id)
            .join(Membership, Membership.club_id == Issue.club_id)
            .join(raiser, raiser.id == Issue.student_id)
            .join(raiser_user, raiser_user.id == raiser.user_id)
            .outerjoin(responder, responder.id == Issue.responded_by)
            .outerjoin(responder_user, responder_user.id == responder.user_id)
            .where(*conditions)
            .order_by(Issue.status, Issue.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        return result.all()

    async def count_open_for_leader(self, student_id: int) -> int:
        result = await self.db.execute(
            select(func.count(Issue.id))
            .join(Membership, Membership.club_id == Issue.club_id)
            .where(
                Membership.student_id == student_id,
                Membership.role == MembershipRole.LEADER,
                Membership.status == MembershipStatus.APPROVED,
                Issue.status != IssueStatus.RESOLVED,
            )
        )
        return result.scalar_one()

    async def set_response(self, issue: Issue, response_body: str, responder_id: int) -> Issue:
        issue.response_body = response_body
        issue.responded_by = responder_id
        issue.responded_at = datetime.now(timezone.utc)
        return issue

    async def set_status(self, issue: Issue, status: IssueStatus) -> Issue:
        issue.status = status
        if status == IssueStatus.RESOLVED:
            issue.resolved_at = datetime.now(timezone.utc)
        return issue
