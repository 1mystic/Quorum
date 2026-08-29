import asyncio
import logging
from datetime import datetime, timezone

from app.core.certificate import (
    CertificateContext, certificate_key, make_serial, render_pdf
)
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.messages import NotificationMessages
from app.core.storage import CERTIFICATE_CONTENT_TYPE, CERTIFICATE_FOLDER, Storage, storage
from app.models import Certificate, NotificationType, RegistrationResult
from app.repository import CertificateRepository, MemberRepository, NotificationRepository
from app.schemas import (
    MyCertificateItem, CertificateDownloadResponse, CertificateVerification
)
from app.exceptions import CertificateNotFoundError, MemberNotFoundError, StorageError

logger = logging.getLogger(__name__)

SERIAL_ATTEMPTS = 5
DOWNLOAD_URL_TTL = 3600
SIGNATORY_ROLE = "Group President"


class CertificateService:
    def __init__(self, certificate_repo: CertificateRepository, member_repo: MemberRepository,
                 notification_repo: NotificationRepository, storage: Storage):
        self.certificate_repo = certificate_repo
        self.member_repo = member_repo
        self.notification_repo = notification_repo
        self.storage = storage

    async def request(self, registration_id: int) -> Certificate | None:
        row = await self.certificate_repo.issue_context(registration_id)
        if row is None:
            return None
        registration, event, group, tenant, member_name, signatory_name = row

        if not registration.checked_in or registration.result == RegistrationResult.REGISTRANT:
            return None

        existing = await self.certificate_repo.get_by_registration_id(registration_id)
        if existing and existing.result == registration.result:
            return existing

        issued_at = datetime.now(timezone.utc)
        serial = existing.serial if existing else await self._reserve_serial(event.title, issued_at)

        pdf = await asyncio.to_thread(render_pdf, CertificateContext(
            serial=serial,
            result=registration.result,
            member_name=member_name,
            event_title=event.title,
            event_date=event.starts_at,
            group_name=group.name,
            tenant_name=tenant.name,
            signatory_name=signatory_name,
            signatory_role=f"{SIGNATORY_ROLE}, {group.name}",
        ))

        # Generation always happens locally either way. Upload to S3 when it's
        # configured; if that fails (e.g. no real AWS credentials yet), fall back to
        # storing the PDF bytes directly in Postgres so certificates still work end to
        # end. Once real S3 credentials are set, uploads succeed again with no code
        # change, and pdf_data simply stays unused for anything issued afterwards.
        stored_locally = False
        try:
            await self.storage.upload(pdf, CERTIFICATE_FOLDER, CERTIFICATE_CONTENT_TYPE,
                                      key=certificate_key(serial))
        except StorageError:
            logger.warning("S3 unavailable, storing certificate %s in Postgres instead", serial)
            stored_locally = True

        if existing:
            updated = await self.certificate_repo.set_result(existing, registration.result)
            await self.certificate_repo.set_pdf_data(updated, pdf if stored_locally else None)
            return updated

        certificate = await self.certificate_repo.create(
            registration_id, serial, registration.result, issued_at
        )
        if stored_locally:
            await self.certificate_repo.set_pdf_data(certificate, pdf)
        await self.notification_repo.create_notification(
            member_id=registration.member_id,
            type=NotificationType.CERTIFICATE_ISSUED,
            message=NotificationMessages.certificate_issued(event.title),
            group_id=event.group_id,
            event_id=event.id,
        )
        return certificate

    async def my_certificates(self, payload: dict) -> list[MyCertificateItem]:
        member = await self._get_member(payload)
        rows = await self.certificate_repo.list_by_member(member.id)
        return [
            MyCertificateItem(
                serial=certificate.serial,
                result=certificate.result,
                event_id=event.id,
                event_title=event.title,
                group_name=group_name,
                issued_at=certificate.issued_at,
                download_url=self._download_url(certificate),
            )
            for certificate, event, group_name in rows
        ]

    async def download(self, payload: dict, serial: str) -> CertificateDownloadResponse:
        member = await self._get_member(payload)
        registration, *_, certificate = await self._by_serial(serial)
        if registration.member_id != member.id:
            raise CertificateNotFoundError()

        return CertificateDownloadResponse(
            serial=certificate.serial,
            filename=f"{certificate.serial}.pdf",
            download_url=self._download_url(certificate),
            expires_in=DOWNLOAD_URL_TTL,
        )

    async def verify(self, serial: str) -> CertificateVerification:
        _, event, group, tenant, member_name, _, certificate = await self._by_serial(serial)
        return CertificateVerification(
            valid=True,
            serial=certificate.serial,
            result=certificate.result,
            member_name=member_name,
            event_title=event.title,
            event_date=event.starts_at,
            group_name=group.name,
            tenant_name=tenant.name,
            issued_at=certificate.issued_at,
            # A certificate serial is already the public credential (same
            # trust model as _download_url/file_bytes below), so the actual
            # rendered PDF can be shown on the public /verify and /cert/view
            # pages without requiring the viewer to be signed in as its owner.
            pdf_url=self._download_url(certificate),
        )

    async def _by_serial(self, serial: str):
        row = await self.certificate_repo.get_by_serial(serial)
        if row is None:
            raise CertificateNotFoundError()
        return row

    async def _reserve_serial(self, event_title: str, issued_at: datetime) -> str:
        for _ in range(SERIAL_ATTEMPTS):
            serial = make_serial(event_title, issued_at)
            if not await self.certificate_repo.serial_exists(serial):
                return serial
        raise RuntimeError(f"could not find a free serial for {event_title!r}")

    def _download_url(self, certificate: Certificate) -> str:
        if certificate.pdf_data is not None:
            # Same trust model as the public verify-by-serial route: the serial is
            # itself the unguessable credential, same as an S3 presigned URL. The
            # frontend opens download_url directly via window.open with no auth
            # header attached, so this route can't require one either.
            return f"{settings.BACKEND_BASE_URL}/certificates/{certificate.serial}/file"
        return self.storage.get_url(certificate_key(certificate.serial), signed=True,
                                    expires_in=DOWNLOAD_URL_TTL)

    async def file_bytes(self, serial: str) -> bytes:
        row = await self.certificate_repo.get_by_serial(serial)
        if row is None:
            raise CertificateNotFoundError()
        certificate = row[-1]
        if certificate.pdf_data is None:
            raise CertificateNotFoundError()
        return certificate.pdf_data

    async def _get_member(self, payload: dict):
        member = await self.member_repo.get_member_by_user_id(int(payload.get("sub")))
        if not member:
            raise MemberNotFoundError()
        return member


async def issue_certificate_job(registration_id: int) -> None:
    async with SessionLocal() as db:
        service = CertificateService(
            CertificateRepository(db), MemberRepository(db), NotificationRepository(db), storage
        )
        try:
            await service.request(registration_id)
            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception("certificate issuing failed for registration %s", registration_id)
