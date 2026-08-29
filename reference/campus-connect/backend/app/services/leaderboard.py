from datetime import datetime, timezone
from app.repository import LeaderboardRepository, UserRepository
from app.schemas import LeaderboardEntry
from app.exceptions import CollegeNotFoundError

POINTS_PER_EVENT = 40
POINTS_PER_NEW_MEMBER = 5
POINTS_PER_ISSUE_RESOLVED = 10
ATTENDANCE_BONUS_MAX = 200


class LeaderboardService:
    def __init__(self, leaderboard_repo: LeaderboardRepository, user_repo: UserRepository):
        self.leaderboard_repo = leaderboard_repo
        self.user_repo = user_repo

    async def get(self, payload: dict) -> list[LeaderboardEntry]:
        college_id = await self._college_id(payload)
        rows = await self.leaderboard_repo.activity_metrics(college_id, self._month_start())

        scored = []
        for club, events_held, new_members, issues_resolved, attendance_rate in rows:
            rate = float(attendance_rate)
            attendance_bonus = round(rate * ATTENDANCE_BONUS_MAX)
            score = (
                events_held * POINTS_PER_EVENT
                + new_members * POINTS_PER_NEW_MEMBER
                + issues_resolved * POINTS_PER_ISSUE_RESOLVED
                + attendance_bonus
            )
            scored.append((club, events_held, new_members, issues_resolved, rate,
                           attendance_bonus, score))

        scored.sort(key=lambda r: (-r[6], -r[2], r[0].name))

        return [
            LeaderboardEntry(
                rank=rank,
                club_id=club.id,
                name=club.name,
                image_url=club.image_url,
                category=club.category,
                score=score,
                events_held=events_held,
                new_members=new_members,
                issues_resolved=issues_resolved,
                attendance_rate=round(rate, 4),
                attendance_bonus=attendance_bonus,
            )
            for rank, (club, events_held, new_members, issues_resolved, rate,
                       attendance_bonus, score) in enumerate(scored, start=1)
        ]

    @staticmethod
    def _month_start() -> datetime:
        now = datetime.now(timezone.utc)
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    async def _college_id(self, payload: dict) -> int:
        college_id = await self.user_repo.get_college_id(int(payload.get("sub")))
        if not college_id:
            raise CollegeNotFoundError()
        return college_id
