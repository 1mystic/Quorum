from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from app.models import (
    Certificate, EventRegistration, Event, Group, Tenant, Member, User, RegistrationResult
)


def _context_query():
    head_member = aliased(Member)
    head_user = aliased(User)
    return (
        select(
            EventRegistration, Event, Group, Tenant,
            User.full_name.label("member_name"),
            head_user.full_name.label("signatory_name"),
        )
        .join(Event, Event.id == EventRegistration.event_id)
        .join(Group, Group.id == Event.group_id)
        .join(Tenant, Tenant.id == Group.tenant_id)
        .join(Member, Member.id == EventRegistration.member_id)
        .join(User, User.id == Member.user_id)
        .join(head_member, head_member.id == Group.group_head)
        .join(head_user, head_user.id == head_member.user_id)
    )


class CertificateRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, registration_id: int, serial: str, result: RegistrationResult,
                     issued_at: datetime) -> Certificate:
        # tenant_id derived from the registration's event/group, never from the caller.
        tenant_id = (await self.db.execute(
            select(EventRegistration.tenant_id).where(EventRegistration.id == registration_id)
        )).scalar_one()
        new_certificate = Certificate(
            tenant_id=tenant_id,
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

    async def list_by_member(self, member_id: int) -> list[tuple[Certificate, Event, str]]:
        result = await self.db.execute(
            select(Certificate, Event, Group.name)
            .join(EventRegistration, EventRegistration.id == Certificate.registration_id)
            .join(Event, Event.id == EventRegistration.event_id)
            .join(Group, Group.id == Event.group_id)
            .where(EventRegistration.member_id == member_id)
            .order_by(Certificate.issued_at.desc())
        )
        return result.all()
