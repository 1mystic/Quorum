from sqlalchemy.exc import IntegrityError
from app.repository import (
    MembershipRepository, ClubRepository, StudentRepository, NotificationRepository
)
from app.models import ClubStatus, MembershipRole, MembershipStatus, NotificationType
from app.schemas import (
    JoinResponse, RequestActionRequest, RequestActionResponse, PendingRequestItem, MemberItem,
    RemoveMemberResponse
)
from app.exceptions import (
    ClubNotFoundError, ClubNotActiveError, NotClubLeaderError, AlreadyMemberError,
    MembershipNotFoundError, ClubActionNotAllowedError, StudentNotFoundError
)
from app.core.messages import MembershipMessages, NotificationMessages


class MembershipService:
    def __init__(self, membership_repo: MembershipRepository, club_repo: ClubRepository,
                 student_repo: StudentRepository, notification_repo: NotificationRepository):
        self.membership_repo = membership_repo
        self.club_repo = club_repo
        self.student_repo = student_repo
        self.notification_repo = notification_repo

    async def join(self, payload: dict, club_id: int) -> JoinResponse:
        student = await self._get_student(payload)
        club = await self.club_repo.get_by_id(club_id)
        if not club:
            raise ClubNotFoundError()
        if club.status != ClubStatus.ACTIVE:
            raise ClubNotActiveError()

        existing = await self.membership_repo.get(student.id, club_id)
        if existing:
            raise AlreadyMemberError()

        try:
            membership = await self.membership_repo.create_membership(
                student_id=student.id,
                club_id=club_id,
                role=MembershipRole.MEMBER,
                status=MembershipStatus.PENDING,
            )
        except IntegrityError:
            # uq_membership_student_club: two concurrent joins raced past the check above
            raise AlreadyMemberError()
        return JoinResponse(
            id=membership.id,
            club_id=club_id,
            status=membership.status,
            message=MembershipMessages.JOIN_REQUESTED,
        )

    async def pending_requests(self, payload: dict, club_id: int) -> list[PendingRequestItem]:
        student = await self._get_student(payload)
        await self._assert_leader(student.id, club_id)
        rows = await self.membership_repo.get_pending_by_club(club_id)
        return [
            PendingRequestItem(
                id=membership.id,
                student_id=membership.student_id,
                full_name=full_name,
                role=membership.role,
                status=membership.status,
            )
            for membership, full_name in rows
        ]

    async def handle_request(self, payload: dict, club_id: int, membership_id: int,
                             data: RequestActionRequest) -> RequestActionResponse:
        student = await self._get_student(payload)
        await self._assert_leader(student.id, club_id)

        membership = await self.membership_repo.get_by_id(membership_id)
        if not membership or membership.club_id != club_id:
            raise MembershipNotFoundError()
        if membership.status != MembershipStatus.PENDING:
            raise ClubActionNotAllowedError("Request has already been handled")

        await self.membership_repo.set_status(membership, data.action)

        club = await self.club_repo.get_by_id(club_id)
        approved = data.action == MembershipStatus.APPROVED
        await self.notification_repo.create_notification(
            student_id=membership.student_id,
            type=NotificationType.JOIN_APPROVED if approved else NotificationType.JOIN_REJECTED,
            message=(
                NotificationMessages.join_approved(club.name) if approved
                else NotificationMessages.join_rejected(club.name)
            ),
            club_id=club_id,
        )

        message = (
            MembershipMessages.REQUEST_APPROVED
            if approved
            else MembershipMessages.REQUEST_REJECTED
        )
        return RequestActionResponse(
            id=membership.id,
            student_id=membership.student_id,
            club_id=membership.club_id,
            status=membership.status,
            message=message,
        )

    async def members(self, club_id: int) -> list[MemberItem]:
        club = await self.club_repo.get_by_id(club_id)
        if not club:
            raise ClubNotFoundError()
        rows = await self.membership_repo.get_members_by_club(club_id)
        return [
            MemberItem(
                id=membership.id,
                student_id=membership.student_id,
                full_name=full_name,
                role=membership.role,
            )
            for membership, full_name in rows
        ]

    async def remove_member(self, payload: dict, club_id: int, student_id: int) -> RemoveMemberResponse:
        student = await self._get_student(payload)
        await self._assert_leader(student.id, club_id)

        membership = await self.membership_repo.get(student_id, club_id)
        if not membership or membership.status != MembershipStatus.APPROVED:
            raise MembershipNotFoundError()
        if membership.role == MembershipRole.LEADER:
            raise ClubActionNotAllowedError("The club leader cannot be removed from their own club")

        membership_id = membership.id
        await self.membership_repo.delete(membership)

        return RemoveMemberResponse(
            id=membership_id,
            student_id=student_id,
            club_id=club_id,
            message=MembershipMessages.MEMBER_REMOVED,
        )

    async def leave(self, payload: dict, club_id: int) -> RemoveMemberResponse:
        """A member leaving a club of their own accord - the self-service
        counterpart to remove_member, which only a leader can do to someone
        else. A leader cannot leave their own club this way; they would need
        to hand off leadership or delete the club instead."""
        student = await self._get_student(payload)

        membership = await self.membership_repo.get(student.id, club_id)
        if not membership or membership.status != MembershipStatus.APPROVED:
            raise MembershipNotFoundError()
        if membership.role == MembershipRole.LEADER:
            raise ClubActionNotAllowedError("The club leader cannot leave their own club")

        membership_id = membership.id
        await self.membership_repo.delete(membership)

        return RemoveMemberResponse(
            id=membership_id,
            student_id=student.id,
            club_id=club_id,
            message=MembershipMessages.LEFT_CLUB,
        )

    async def _get_student(self, payload: dict):
        student = await self.student_repo.get_student_by_user_id(int(payload.get("sub")))
        if not student:
            raise StudentNotFoundError()
        return student

    async def _assert_leader(self, student_id: int, club_id: int):
        if not await self.membership_repo.is_leader(student_id, club_id):
            raise NotClubLeaderError()
