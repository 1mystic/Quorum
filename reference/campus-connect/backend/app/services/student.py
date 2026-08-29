from fastapi import UploadFile
from app.repository import StudentRepository, UserRepository, MembershipRepository
from app.models import ClubStatus, MembershipStatus, Student
from app.schemas import (
    StudentClubItem, PublicStudentResponse, StudentProfileResponse, UpdateProfileRequest,
    UpdateProfileResponse
)
from app.exceptions import StudentNotFoundError
from app.core.messages import StudentMessages
from app.core.storage import Storage, AVATAR_FOLDER


class StudentService:
    def __init__(self, student_repo: StudentRepository, user_repo: UserRepository,
                 membership_repo: MembershipRepository, storage: Storage):
        self.student_repo = student_repo
        self.user_repo = user_repo
        self.membership_repo = membership_repo
        self.storage = storage

    async def my_profile(self, payload: dict) -> StudentProfileResponse:
        student = await self._me(payload)
        return StudentProfileResponse(
            **self._profile_fields(student),
            joined_clubs=await self._joined_clubs(student.id),
        )

    async def update_my_profile(self, payload: dict, data: UpdateProfileRequest,
                                image: UploadFile | None = None) -> UpdateProfileResponse:
        student = await self._me(payload)
        await self.student_repo.update_profile(student, data.model_dump(exclude_unset=True))
        if image is not None:
            old_url = student.user.profile_image_url
            new_url = await self.storage.upload_image(image, AVATAR_FOLDER)
            await self.user_repo.set_profile_image(student.user, new_url)
            await self.storage.delete_url(old_url)
        return UpdateProfileResponse(
            **self._profile_fields(student),
            joined_clubs=await self._joined_clubs(student.id),
            message=StudentMessages.PROFILE_UPDATED,
        )

    async def public_profile(self, payload: dict, student_id: int) -> PublicStudentResponse:
        college_id = await self.user_repo.get_college_id(int(payload.get("sub")))
        student = await self.student_repo.get_by_id_with_user(student_id)
        if not student or college_id is None or student.user.college_id != college_id:
            raise StudentNotFoundError()

        return PublicStudentResponse(
            student_id=student.id,
            full_name=student.user.full_name,
            profile_image_url=student.user.profile_image_url,
            branch=student.branch,
            year=student.year,
            joined_clubs=await self._joined_clubs(student.id),
        )

    async def _joined_clubs(self, student_id: int) -> list[StudentClubItem]:
        rows = await self.membership_repo.list_by_student(
            student_id,
            membership_status=MembershipStatus.APPROVED,
            club_status=ClubStatus.ACTIVE,
        )
        return [
            StudentClubItem(
                club_id=club.id,
                name=club.name,
                category=club.category,
                membership_role=membership.role,
                joined_at=membership.created_at,
            )
            for membership, club, _member_count, _head_name in rows
        ]

    @staticmethod
    def _profile_fields(student: Student) -> dict:
        return {
            "student_id": student.id,
            "full_name": student.user.full_name,
            "email": student.user.email,
            "profile_image_url": student.user.profile_image_url,
            "bio": student.bio,
            "interests": student.interests,
            "roll_no": student.roll_no,
            "branch": student.branch,
            "year": student.year,
            "created_at": student.created_at,
        }

    async def _me(self, payload: dict) -> Student:
        student = await self.student_repo.get_by_user_id_with_user(int(payload.get("sub")))
        if not student:
            raise StudentNotFoundError()
        return student
