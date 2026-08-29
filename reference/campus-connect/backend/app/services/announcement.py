from datetime import datetime
from app.repository import (
    AnnouncementRepository, ClubRepository, MembershipRepository,
    StudentRepository, UserRepository
)
from app.models import Announcement, AnnouncementCategory, ClubStatus, MembershipRole
from app.schemas import (
    CreateAnnouncementRequest, PinAnnouncementRequest, CreateAnnouncementResponse,
    AnnouncementItem, PinAnnouncementResponse, DeleteAnnouncementResponse,
    UnreadCountResponse, MarkAnnouncementsReadResponse
)
from app.exceptions import (
    AnnouncementNotFoundError, ClubNotFoundError, ClubNotActiveError,
    NotClubLeaderError, StudentNotFoundError, CollegeNotFoundError
)
from app.core.messages import AnnouncementMessages


class AnnouncementService:
    def __init__(self, announcement_repo: AnnouncementRepository, club_repo: ClubRepository,
                 membership_repo: MembershipRepository, student_repo: StudentRepository,
                 user_repo: UserRepository):
        self.announcement_repo = announcement_repo
        self.club_repo = club_repo
        self.membership_repo = membership_repo
        self.student_repo = student_repo
        self.user_repo = user_repo

    async def create(self, payload: dict, data: CreateAnnouncementRequest) -> CreateAnnouncementResponse:
        student = await self._get_student(payload)
        college_id = await self._college_id(payload)

        club = await self.club_repo.get_by_id(data.club_id)
        if not club or club.college_id != college_id:
            raise ClubNotFoundError()
        if club.status != ClubStatus.ACTIVE:
            raise ClubNotActiveError()
        if not await self.membership_repo.is_leader(student.id, club.id):
            raise NotClubLeaderError()

        announcement = await self.announcement_repo.create_announcement(
            club_id=club.id,
            author_id=student.id,
            title=data.title,
            body=data.body,
            category=data.category,
            is_pinned=data.is_pinned,
        )
        return CreateAnnouncementResponse(
            id=announcement.id, club_id=club.id, title=announcement.title,
            category=announcement.category, is_pinned=announcement.is_pinned,
            message=AnnouncementMessages.POSTED,
        )

    async def feed(self, payload: dict, club_id: int | None = None,
                   category: AnnouncementCategory | None = None, search: str | None = None,
                   limit: int = 50, offset: int = 0) -> list[AnnouncementItem]:
        student = await self._get_student(payload)
        rows = await self.announcement_repo.list_for_student(
            student.id, club_id=club_id, category=category, search=search,
            limit=limit, offset=offset
        )
        return self._to_items(rows, student.announcements_seen_at)

    async def mine(self, payload: dict, club_id: int | None = None,
                   category: AnnouncementCategory | None = None, search: str | None = None,
                   limit: int = 50, offset: int = 0) -> list[AnnouncementItem]:
        student = await self._get_student(payload)
        rows = await self.announcement_repo.list_for_student(
            student.id, role=MembershipRole.LEADER, club_id=club_id,
            category=category, search=search, limit=limit, offset=offset
        )
        return self._to_items(rows, student.announcements_seen_at)

    async def unread_count(self, payload: dict) -> UnreadCountResponse:
        student = await self._get_student(payload)
        count = await self.announcement_repo.count_unread(
            student.id, student.announcements_seen_at
        )
        return UnreadCountResponse(count=count)

    async def pin(self, payload: dict, announcement_id: int,
                  data: PinAnnouncementRequest) -> PinAnnouncementResponse:
        announcement = await self._managed_announcement(payload, announcement_id)
        await self.announcement_repo.set_pinned(announcement, data.pinned)
        message = AnnouncementMessages.PINNED if data.pinned else AnnouncementMessages.UNPINNED
        return PinAnnouncementResponse(
            id=announcement.id, title=announcement.title,
            is_pinned=announcement.is_pinned, message=message,
        )

    async def delete(self, payload: dict, announcement_id: int) -> DeleteAnnouncementResponse:
        announcement = await self._managed_announcement(payload, announcement_id)
        await self.announcement_repo.delete_announcement(announcement)
        return DeleteAnnouncementResponse(
            id=announcement_id, message=AnnouncementMessages.DELETED,
        )

    async def mark_read(self, payload: dict) -> MarkAnnouncementsReadResponse:
        student = await self._get_student(payload)
        await self.student_repo.mark_announcements_seen(student)
        return MarkAnnouncementsReadResponse(
            seen_at=student.announcements_seen_at,
            message=AnnouncementMessages.MARKED_READ,
        )

    @staticmethod
    def _to_items(rows: list[tuple[Announcement, str, str]],
                  seen_at: datetime | None) -> list[AnnouncementItem]:
        return [
            AnnouncementItem(
                id=announcement.id,
                club_id=announcement.club_id,
                club_name=club_name,
                author_id=announcement.author_id,
                author_name=author_name,
                title=announcement.title,
                body=announcement.body,
                category=announcement.category,
                is_pinned=announcement.is_pinned,
                unread=seen_at is None or announcement.created_at > seen_at,
                created_at=announcement.created_at,
            )
            for announcement, club_name, author_name in rows
        ]

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

    async def _managed_announcement(self, payload: dict, announcement_id: int) -> Announcement:
        student = await self._get_student(payload)
        announcement = await self.announcement_repo.get_by_id(announcement_id)
        if not announcement:
            raise AnnouncementNotFoundError()
        if announcement.club.college_id != await self._college_id(payload):
            raise AnnouncementNotFoundError()
        if not await self.membership_repo.is_leader(student.id, announcement.club_id):
            raise NotClubLeaderError()
        return announcement
