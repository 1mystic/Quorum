from datetime import datetime
from sqlalchemy import select, func, cast, Float
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import (
    Club, ClubStatus, Event, EventStatus, EventRegistration,
    Membership, MembershipStatus, Issue, IssueStatus,
)


class LeaderboardRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def activity_metrics(self, college_id: int, since: datetime):
        events_sub = (
            select(
                Event.club_id.label("club_id"),
                func.count(Event.id).label("events_held"),
            )
            .where(Event.status == EventStatus.PUBLISHED, Event.starts_at >= since)
            .group_by(Event.club_id)
            .subquery()
        )

        members_sub = (
            select(
                Membership.club_id.label("club_id"),
                func.count(Membership.id).label("new_members"),
            )
            .where(Membership.status == MembershipStatus.APPROVED, Membership.created_at >= since)
            .group_by(Membership.club_id)
            .subquery()
        )

        issues_sub = (
            select(
                Issue.club_id.label("club_id"),
                func.count(Issue.id).label("issues_resolved"),
            )
            .where(Issue.status == IssueStatus.RESOLVED, Issue.resolved_at >= since)
            .group_by(Issue.club_id)
            .subquery()
        )

        # per-event attendance rate; the inner join drops events with no registrations
        event_rates = (
            select(
                Event.club_id.label("club_id"),
                (cast(
                    func.count(EventRegistration.id).filter(EventRegistration.checked_in), Float
                ) / func.count(EventRegistration.id)).label("rate"),
            )
            .join(EventRegistration, EventRegistration.event_id == Event.id)
            .where(Event.status == EventStatus.PUBLISHED, Event.starts_at >= since)
            .group_by(Event.id, Event.club_id)
            .subquery()
        )

        attendance_sub = (
            select(
                event_rates.c.club_id.label("club_id"),
                func.avg(event_rates.c.rate).label("attendance_rate"),
            )
            .group_by(event_rates.c.club_id)
            .subquery()
        )

        result = await self.db.execute(
            select(
                Club,
                func.coalesce(events_sub.c.events_held, 0),
                func.coalesce(members_sub.c.new_members, 0),
                func.coalesce(issues_sub.c.issues_resolved, 0),
                func.coalesce(attendance_sub.c.attendance_rate, 0.0),
            )
            .outerjoin(events_sub, events_sub.c.club_id == Club.id)
            .outerjoin(members_sub, members_sub.c.club_id == Club.id)
            .outerjoin(issues_sub, issues_sub.c.club_id == Club.id)
            .outerjoin(attendance_sub, attendance_sub.c.club_id == Club.id)
            .where(Club.college_id == college_id, Club.status == ClubStatus.ACTIVE)
        )
        return result.all()
