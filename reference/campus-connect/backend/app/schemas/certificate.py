from datetime import datetime
from pydantic import BaseModel
from app.models import RegistrationResult


class MyCertificateItem(BaseModel):
    serial: str
    result: RegistrationResult
    event_id: int
    event_title: str
    club_name: str
    issued_at: datetime
    download_url: str


class CertificateDownloadResponse(BaseModel):
    serial: str
    filename: str
    download_url: str
    expires_in: int


class CertificateVerification(BaseModel):
    valid: bool
    serial: str
    result: RegistrationResult
    student_name: str
    event_title: str
    event_date: datetime
    club_name: str
    college_name: str
    issued_at: datetime
    pdf_url: str
