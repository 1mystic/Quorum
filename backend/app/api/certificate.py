from fastapi import APIRouter, Depends, Response, Security
from app.schemas import (
    MyCertificateItem, CertificateDownloadResponse, CertificateVerification
)
from app.services import CertificateService
from app.core.di import get_certificate_service, get_user_info

certificate_router = APIRouter(prefix="/certificates", tags=["Certificates"])

# Deliberately outside /api/t/{slug}: a certificate serial is globally unique
# and verification is meant to work for an anonymous verifier with no tenant
# context and no token at all (that is the point of a QR-code verify page).
public_certificate_router = APIRouter(prefix="/public/certificates", tags=["Certificates (public)"])


@certificate_router.get("/me", response_model=list[MyCertificateItem])
async def my_certificates(
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: CertificateService = Depends(get_certificate_service),
):
    return await service.my_certificates(payload)


@public_certificate_router.get("/verify/{serial}", response_model=CertificateVerification,
                        description="Public: confirms a serial is authentic, no login required")
async def verify_certificate(
    serial: str,
    service: CertificateService = Depends(get_certificate_service),
):
    return await service.verify(serial)


@certificate_router.get("/{serial}/download", response_model=CertificateDownloadResponse)
async def download_certificate(
    serial: str,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: CertificateService = Depends(get_certificate_service),
):
    return await service.download(payload, serial)


@public_certificate_router.get("/{serial}/file",
                        description="Public, same trust model as /verify/{serial} - serves the "
                                    "raw PDF for a certificate that fell back to Postgres storage "
                                    "because S3 was not configured. Not used once real AWS "
                                    "credentials make S3 uploads succeed.")
async def download_certificate_file(
    serial: str,
    service: CertificateService = Depends(get_certificate_service),
):
    pdf = await service.file_bytes(serial)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{serial}.pdf"'},
    )
