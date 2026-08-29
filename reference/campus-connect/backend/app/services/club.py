from fastapi import UploadFile
from app.repository import ClubRepository, StudentRepository, UserRepository, MembershipRepository
from app.models import Club, ClubType, ClubStatus, MembershipRole, MembershipStatus, UserRole
from app.schemas import (
    CreateClubRequest, UpdateClubRequest, CreateClubResponse, ClubStatusResponse,
    ClubListItem, ClubDetailResponse, ClubLinkSchema, ClubHeadInfo, MyClubItem, TrendingClubItem
)
from app.exceptions import (
    ClubNotFoundError, NotClubLeaderError, ClubActionNotAllowedError, StudentNotFoundError,
    CollegeNotFoundError, InvalidStatusFilterError
)
from app.core.messages import ClubMessages
from app.core.storage import Storage, CLUB_FOLDER


class ClubService:
    def __init__(self, club_repo: ClubRepository, student_repo: StudentRepository,
                 user_repo: UserRepository, membership_repo: MembershipRepository,
                 storage: Storage):
        self.club_repo = club_repo
        self.student_repo = student_repo
        self.user_repo = user_repo
        self.membership_repo = membership_repo
        self.storage = storage

    async def create(self, payload: dict, data: CreateClubRequest,
                     image: UploadFile | None = None) -> CreateClubResponse:
        user_id = int(payload.get("sub"))
        student = await self.student_repo.get_student_by_user_id(user_id)
        if not student:
            raise StudentNotFoundError()

        college_id = await self._college_id(payload)
        status = ClubStatus.ACTIVE if data.type == ClubType.UNOFFICIAL else ClubStatus.PENDING

        image_url = await self.storage.upload_image(image, CLUB_FOLDER) if image else None
        club = await self.club_repo.create_club(
            college_id=college_id,
            club_head=student.id,
            name=data.name,
            description=data.description,
            category=data.category,
            type=data.type,
            status=status,
            image_url=image_url,
        )
        for link in data.links:
            await self.club_repo.add_link(club.id, link.label, link.url)

        await self.membership_repo.create_membership(
            student_id=student.id,
            club_id=club.id,
            role=MembershipRole.LEADER,
            status=MembershipStatus.APPROVED,
        )

        message = ClubMessages.CREATED_ACTIVE if status == ClubStatus.ACTIVE else ClubMessages.CREATED_PENDING
        return CreateClubResponse(id=club.id, name=club.name, type=club.type, status=club.status, message=message)

    
    async def my_clubs(self, payload: dict, role: MembershipRole | None = None,
                       status: str | None = None) -> list[MyClubItem]:
        student = await self._get_student(payload)
        club_status, membership_status = self._resolve_status(role, status)
        rows = await self.membership_repo.list_by_student(
            student.id, role, membership_status=membership_status, club_status=club_status
        )
        return [
            MyClubItem(
                id=club.id,
                name=club.name,
                description=club.description,
                category=club.category,
                type=club.type,
                status=club.status,
                image_url=club.image_url,
                member_count=count,
                head_name=head_name,
                created_at=club.created_at,
                links=[
                    ClubLinkSchema(label=link.label, url=link.url)
                    for link in club.links
                ],
                membership_id=membership.id,
                membership_role=membership.role,
                membership_status=membership.status,
                joined_at=membership.created_at,
            )
            for membership, club, count, head_name in rows
        ]

    async def trending(self, limit: int = 8) -> list[TrendingClubItem]:
        rows = await self.club_repo.list_trending(limit)
        return [
            TrendingClubItem(
                id=club.id,
                name=club.name,
                category=club.category,
                member_count=count,
                college_name=college_name,
                college_slug=college_slug,
            )
            for club, count, college_name, college_slug in rows
        ]

    async def list(self, payload: dict, status: ClubStatus | None = None,
                   search: str | None = None, category: str | None = None,
                   type: ClubType | None = None) -> list[ClubListItem]:
        college_id = await self._college_id(payload)
        effective_status = status if self._is_admin(payload) else ClubStatus.ACTIVE

        rows = await self.club_repo.list_by_college(college_id, effective_status, search, category, type)
        return [
            ClubListItem(
                id=club.id,
                name=club.name,
                description=club.description,
                category=club.category,
                type=club.type,
                status=club.status,
                image_url=club.image_url,
                member_count=count,
                head_name=head_name,
                created_at=club.created_at,
                links=[
                    ClubLinkSchema(label=link.label, url=link.url)
                    for link in club.links
                ],
            )
            for club, count, head_name in rows
        ]

    async def get(self, payload: dict, club_id: int) -> ClubDetailResponse:
        club = await self.club_repo.get_by_id(club_id)
        if not club:
            raise ClubNotFoundError()

        college_id = await self._college_id(payload)
        if club.college_id != college_id:
            raise ClubNotFoundError()

        is_admin = self._is_admin(payload)
        if not is_admin and club.status != ClubStatus.ACTIVE:
            raise ClubNotFoundError()

        return await self._detail(club, include_contact=is_admin)

    async def update(self, payload: dict, club_id: int, data: UpdateClubRequest,
                     image: UploadFile | None = None) -> ClubDetailResponse:
        student = await self._get_student(payload)
        club = await self.club_repo.get_by_id(club_id)
        if not club:
            raise ClubNotFoundError()
        if not await self.membership_repo.is_leader(student.id, club_id):
            raise NotClubLeaderError()

        old_image_url = club.image_url
        new_image_url = await self.storage.upload_image(image, CLUB_FOLDER) if image else data.image_url
        await self.club_repo.update_club(club, data.description, data.category, new_image_url)
        if new_image_url:
            await self.storage.delete_url(old_image_url)
        if data.links is not None:
            await self.club_repo.replace_links(club_id, data.links)

        updated = await self.club_repo.get_by_id(club_id)
        return await self._detail(updated, include_contact=False)

    async def delete(self, payload: dict, club_id: int) -> ClubStatusResponse:
        student = await self._get_student(payload)
        club = await self.club_repo.get_by_id(club_id)
        if not club:
            raise ClubNotFoundError()
        if not await self.membership_repo.is_leader(student.id, club_id):
            raise NotClubLeaderError()

        await self.club_repo.set_status(club, ClubStatus.ARCHIVED)
        return ClubStatusResponse(id=club.id, name=club.name, status=club.status, message=ClubMessages.ARCHIVED)

    async def approve(self, payload: dict, club_id: int) -> ClubStatusResponse:
        club = await self._admin_pending_club(payload, club_id)
        await self.club_repo.set_status(club, ClubStatus.ACTIVE)
        return ClubStatusResponse(id=club.id, name=club.name, status=club.status, message=ClubMessages.APPROVED)

    async def reject(self, payload: dict, club_id: int) -> ClubStatusResponse:
        club = await self._admin_pending_club(payload, club_id)
        await self.club_repo.set_status(club, ClubStatus.REJECTED)
        return ClubStatusResponse(id=club.id, name=club.name, status=club.status, message=ClubMessages.REJECTED)

    @staticmethod
    def _resolve_status(role: MembershipRole | None, status: str | None):
        if status is None:
            return None, None
        if role is None:
            raise InvalidStatusFilterError(ClubMessages.STATUS_NEEDS_ROLE)

        is_leader = role == MembershipRole.LEADER
        options = ClubStatus if is_leader else MembershipStatus
        try:
            parsed = options(status)
        except ValueError:
            allowed = ", ".join(option.value for option in options)
            raise InvalidStatusFilterError(
                f"status must be one of {allowed} when role is {role.value}"
            )
        return (parsed, None) if is_leader else (None, parsed)

    @staticmethod
    def _is_admin(payload: dict) -> bool:
        return payload.get("role") == UserRole.CAMPUS_ADMIN

    async def _college_id(self, payload: dict) -> int:
        college_id = await self.user_repo.get_college_id(int(payload.get("sub")))
        if not college_id:
            raise CollegeNotFoundError()
        return college_id

    async def _detail(self, club: Club, include_contact: bool) -> ClubDetailResponse:
        member_count = await self.club_repo.count_members(club.id)
        return ClubDetailResponse(
            id=club.id,
            name=club.name,
            description=club.description,
            category=club.category,
            type=club.type,
            status=club.status,
            image_url=club.image_url,
            member_count=member_count,
            created_at=club.created_at,
            links=[ClubLinkSchema(label=link.label, url=link.url) for link in club.links],
            head=self._head_info(club, include_contact),
        )

    @staticmethod
    def _head_info(club: Club, include_contact: bool) -> ClubHeadInfo:
        head = club.head
        return ClubHeadInfo(
            student_id=head.id,
            full_name=head.user.full_name,
            email=head.user.email if include_contact else None,
            roll_no=head.roll_no if include_contact else None,
            branch=head.branch if include_contact else None,
            year=head.year if include_contact else None,
        )

    async def _get_student(self, payload: dict):
        student = await self.student_repo.get_student_by_user_id(int(payload.get("sub")))
        if not student:
            raise StudentNotFoundError()
        return student

    async def _admin_pending_club(self, payload: dict, club_id: int):
        club = await self.club_repo.get_by_id(club_id)
        if not club:
            raise ClubNotFoundError()
        college_id = await self._college_id(payload)
        if club.college_id != college_id:
            raise ClubActionNotAllowedError()
        if club.status != ClubStatus.PENDING:
            raise ClubActionNotAllowedError("Club is not pending approval")
        return club
