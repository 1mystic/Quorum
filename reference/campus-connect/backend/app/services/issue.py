from app.repository import (
    IssueRepository, ClubRepository, EventRepository, MembershipRepository,
    StudentRepository, UserRepository
)
from app.models import Issue, IssueStatus, ClubStatus
from app.schemas import (
    RaiseIssueRequest, ReplyIssueRequest, RaiseIssueResponse, IssueResponseInfo,
    MyIssueItem, LeaderIssueItem, IssueActionResponse, OpenIssueCountResponse
)
from app.exceptions import (
    IssueNotFoundError, IssueActionNotAllowedError, ClubNotFoundError, ClubNotActiveError,
    NotClubLeaderError, StudentNotFoundError, CollegeNotFoundError, EventNotFoundError
)
from app.core.messages import IssueMessages


class IssueService:
    def __init__(self, issue_repo: IssueRepository, club_repo: ClubRepository,
                 event_repo: EventRepository, membership_repo: MembershipRepository,
                 student_repo: StudentRepository, user_repo: UserRepository):
        self.issue_repo = issue_repo
        self.club_repo = club_repo
        self.event_repo = event_repo
        self.membership_repo = membership_repo
        self.student_repo = student_repo
        self.user_repo = user_repo

    async def raise_issue(self, payload: dict, data: RaiseIssueRequest) -> RaiseIssueResponse:
        student = await self._get_student(payload)
        college_id = await self._college_id(payload)

        club = await self.club_repo.get_by_id(data.club_id)
        if not club or club.college_id != college_id:
            raise ClubNotFoundError()
        if club.status != ClubStatus.ACTIVE:
            raise ClubNotActiveError()

        if data.event_id is not None:
            event = await self.event_repo.get_by_id(data.event_id)
            if not event or event.club_id != club.id:
                raise EventNotFoundError()

        issue = await self.issue_repo.create_issue(
            student_id=student.id,
            club_id=club.id,
            event_id=data.event_id,
            category=data.category,
            title=data.title,
            description=data.description,
        )
        return RaiseIssueResponse(
            id=issue.id, club_id=club.id, title=issue.title, category=issue.category,
            status=issue.status, message=IssueMessages.RAISED,
        )

    async def my_issues(self, payload: dict, status: IssueStatus | None = None,
                        club_id: int | None = None, limit: int = 50,
                        offset: int = 0) -> list[MyIssueItem]:
        student = await self._get_student(payload)
        rows = await self.issue_repo.list_by_student(
            student.id, status=status, club_id=club_id, limit=limit, offset=offset
        )
        return [
            MyIssueItem(
                id=issue.id,
                club_id=issue.club_id,
                club_name=club_name,
                event_id=issue.event_id,
                category=issue.category,
                status=issue.status,
                title=issue.title,
                description=issue.description,
                response=self._response_info(issue, responder_name),
                created_at=issue.created_at,
                resolved_at=issue.resolved_at,
            )
            for issue, club_name, responder_name in rows
        ]

    async def club_queue(self, payload: dict, status: IssueStatus | None = None,
                         club_id: int | None = None, limit: int = 50,
                         offset: int = 0) -> list[LeaderIssueItem]:
        student = await self._get_student(payload)
        rows = await self.issue_repo.list_for_leader(
            student.id, status=status, club_id=club_id, limit=limit, offset=offset
        )
        return [
            LeaderIssueItem(
                id=issue.id,
                club_id=issue.club_id,
                club_name=club_name,
                student_id=issue.student_id,
                raised_by=raised_by,
                event_id=issue.event_id,
                category=issue.category,
                status=issue.status,
                title=issue.title,
                description=issue.description,
                response=self._response_info(issue, responder_name),
                created_at=issue.created_at,
                resolved_at=issue.resolved_at,
            )
            for issue, club_name, raised_by, responder_name in rows
        ]

    async def open_count(self, payload: dict) -> OpenIssueCountResponse:
        student = await self._get_student(payload)
        count = await self.issue_repo.count_open_for_leader(student.id)
        return OpenIssueCountResponse(count=count)

    async def reply(self, payload: dict, issue_id: int,
                    data: ReplyIssueRequest) -> IssueActionResponse:
        student = await self._get_student(payload)
        issue = await self._managed_issue(payload, issue_id)
        if issue.status == IssueStatus.RESOLVED:
            raise IssueActionNotAllowedError("A resolved issue cannot be replied to")

        await self.issue_repo.set_response(issue, data.reply, student.id)
        await self.issue_repo.set_status(issue, IssueStatus.IN_PROGRESS)
        return IssueActionResponse(
            id=issue.id, status=issue.status, message=IssueMessages.REPLIED,
        )

    async def resolve(self, payload: dict, issue_id: int) -> IssueActionResponse:
        issue = await self._managed_issue(payload, issue_id)
        if issue.status == IssueStatus.RESOLVED:
            raise IssueActionNotAllowedError("Issue is already resolved")

        await self.issue_repo.set_status(issue, IssueStatus.RESOLVED)
        return IssueActionResponse(
            id=issue.id, status=issue.status, message=IssueMessages.RESOLVED,
        )

    @staticmethod
    def _response_info(issue: Issue, responder_name: str | None) -> IssueResponseInfo | None:
        if not issue.response_body:
            return None
        return IssueResponseInfo(
            by=responder_name or "",
            text=issue.response_body,
            at=issue.responded_at,
        )

    async def _get_student(self, payload: dict):
        student = await self.student_repo.get_student_by_user_id(int(payload.get("sub")))
        if not student:
            raise StudentNotFoundError()
        return student

    async def _college_id(self, payload: dict) -> int:
        college_id = await self.user_repo.get_college_id(int(payload.get("sub")))
        if not college_id:
            raise CollegeNotFoundError()
        return college_id

    async def _managed_issue(self, payload: dict, issue_id: int) -> Issue:
        student = await self._get_student(payload)
        issue = await self.issue_repo.get_by_id(issue_id)
        if not issue:
            raise IssueNotFoundError()
        if issue.club.college_id != await self._college_id(payload):
            raise IssueNotFoundError()
        if not await self.membership_repo.is_leader(student.id, issue.club_id):
            raise NotClubLeaderError()
        return issue
