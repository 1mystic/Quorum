import re
import secrets
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import cairosvg
import qrcode
from jinja2 import Environment, FileSystemLoader, select_autoescape
from qrcode.image.svg import SvgPathImage

from app.core.config import settings
from app.core.storage import CERTIFICATE_FOLDER
from app.models import RegistrationResult


TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "certificates"

TEMPLATES = {
    RegistrationResult.WINNER: "winner.svg",
    RegistrationResult.RUNNER_UP: "runner_up.svg",
    RegistrationResult.PARTICIPANT: "participant.svg",
}

SERIAL_PREFIX = "CC"
_NON_ALNUM = re.compile(r"[^A-Z0-9]+")

NAME_SIZES = ((22, 46), (30, 38), (40, 30), (999, 24))
TITLE_SIZES = ((34, 22), (48, 18), (999, 15))

QR_SIZE = 84


def clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else f"{text[:limit - 1].rstrip()}…"


_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(default=True, default_for_string=True),
    trim_blocks=True,
    lstrip_blocks=True,
)
_env.filters["clip"] = clip


@dataclass(frozen=True)
class CertificateContext:
    serial: str
    result: RegistrationResult
    student_name: str
    event_title: str
    event_date: datetime
    club_name: str
    college_name: str
    signatory_name: str
    signatory_role: str


def abbreviate(event_title: str) -> str:
    words = _NON_ALNUM.sub(" ", event_title.upper()).split()
    letters = "".join(word[0] for word in words[:3])
    return letters or "EVT"


def make_serial(event_title: str, issued_on: datetime) -> str:
    number = f"{secrets.randbelow(100000):05d}"
    return f"{SERIAL_PREFIX}-{abbreviate(event_title)}-{issued_on.year}-{number}"


def certificate_key(serial: str) -> str:
    return f"{CERTIFICATE_FOLDER}/{serial}.pdf"


def verify_url(serial: str) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/verify/{serial}"


def qr_path(data: str) -> tuple[str, int]:
    image = qrcode.make(data, image_factory=SvgPathImage, border=2)
    return image.path.get("d"), image.width + 2 * image.border


def _fit(text: str, sizes: tuple[tuple[int, int], ...]) -> int:
    return next(size for limit, size in sizes if len(text) <= limit)


def render_svg(context: CertificateContext) -> str:
    path, box = qr_path(verify_url(context.serial))
    template = _env.get_template(TEMPLATES[context.result])
    return template.render(
        serial=context.serial,
        student_name=context.student_name,
        event_title=context.event_title,
        club_name=context.club_name,
        college_name=context.college_name,
        event_date=context.event_date.strftime("%B %d, %Y"),
        signatory_name=context.signatory_name,
        signatory_role=context.signatory_role,
        name_size=_fit(context.student_name, NAME_SIZES),
        title_size=_fit(context.event_title, TITLE_SIZES),
        qr_path=path,
        qr_scale=round(QR_SIZE / box, 5),
    )


def render_pdf(context: CertificateContext) -> bytes:
    return cairosvg.svg2pdf(bytestring=render_svg(context).encode("utf-8"))
