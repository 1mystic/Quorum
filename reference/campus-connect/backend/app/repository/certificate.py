from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from app.models import (
    Certificate, EventRegistration, Event, Club, College, Student, User, RegistrationResult
)


def _context_query():
    head_student = aliased(Student)
    head_user = aliased(User)
    return (
        select(
            EventRegistration, Event, Club, College,
            User.full_name.label("student_name"),
            head_user.full_name.label("signatory_name"),
        )
        .join(Event, Event.id == EventRegistration.event_id)
        .join(Club, Club.id == Event.club_id)
        .join(College, College.id == Club.college_id)
        .join(Student, Student.id == EventRegistration.student_id)
        .join(User, User.id == Student.user_id)
        .join(head_student, head_student.id == Club.club_head)
        .join(head_user, head_user.id == head_student.user_id)
    )


class CertificateRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, registration_id: int, serial: str, result: RegistrationResult,
                     issued_at: datetime) -> Certificate:
        new_certificate = Certificate(
            registration_id=registration_id,
            serial=serial,
            result=result,
            issued_at=issued_at,
        )
        self.db.add(new_certificate)
        await self.db.flush()
        return new_certificate

    async def set_result(self, certificate: Certificate,
                         result: RegistrationResult) -> Certificate:
        certificate.result = result
        return certificate

    async def set_pdf_data(self, certificate: Certificate, pdf_data: bytes | None) -> Certificate:
        certificate.pdf_data = pdf_data
        return certificate

    async def get_by_registration_id(self, registration_id: int) -> Certificate | None:
        result = await self.db.execute(
            select(Certificate).where(Certificate.registration_id == registration_id)
        )
        return result.scalar_one_or_none()

    async def serial_exists(self, serial: str) -> bool:
        result = await self.db.execute(
            select(Certificate.id).where(Certificate.serial == serial)
        )
        return result.first() is not None

    async def issue_context(self, registration_id: int):
        result = await self.db.execute(
            _context_query().where(EventRegistration.id == registration_id)
        )
        return result.first()

    async def get_by_serial(self, serial: str):
        result = await self.db.execute(
            _context_query()
            .add_columns(Certificate)
            .join(Certificate, Certificate.registration_id == EventRegistration.id)
            .where(Certificate.serial == serial)
        )
        return result.first()

    async def list_by_student(self, student_id: int) -> list[tuple[Certificate, Event, str]]:
        result = await self.db.execute(
            select(Certificate, Event, Club.name)
            .join(EventRegistration, EventRegistration.id == Certificate.registration_id)
            .join(Event, Event.id == EventRegistration.event_id)
            .join(Club, Club.id == Event.club_id)
            .where(EventRegistration.student_id == student_id)
            .order_by(Certificate.issued_at.desc())
        )
        return result.all()
