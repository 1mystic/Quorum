import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "emails"

APP_NAME = "CampusConnect"
SMTP_TIMEOUT = 15

RESET_TEMPLATE = "reset_password.html"
RESET_SUBJECT = f"Reset your {APP_NAME} password"

_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape(default=True, default_for_string=True),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _reset_text(full_name: str, reset_url: str, expires_minutes: int) -> str:
    return (
        f"Hi {full_name},\n\n"
        f"We received a request to reset your {APP_NAME} password.\n"
        f"Open the link below to choose a new one:\n\n"
        f"{reset_url}\n\n"
        f"This link expires in {expires_minutes} minutes and can only be used once.\n"
        f"If you did not request a password reset, you can ignore this email — "
        f"your password stays unchanged.\n\n"
        f"— The {APP_NAME} team"
    )


class Mailer:
    def send(self, to: str, subject: str, html: str, text: str) -> None:
        message = EmailMessage()
        message["From"] = formataddr((APP_NAME, settings.MAIL_FROM))
        message["To"] = to
        message["Subject"] = subject
        message.set_content(text)
        message.add_alternative(html, subtype="html")

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=SMTP_TIMEOUT) as server:
            server.ehlo()
            try:
                server.starttls()
                server.ehlo()
            except smtplib.SMTPNotSupportedError:
                pass
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(message)

    def send_password_reset(self, to: str, full_name: str, reset_url: str,
                            expires_minutes: int) -> None:
        html = _env.get_template(RESET_TEMPLATE).render(
            app_name=APP_NAME,
            full_name=full_name,
            reset_url=reset_url,
            expires_minutes=expires_minutes,
        )
        self.send(to, RESET_SUBJECT, html, _reset_text(full_name, reset_url, expires_minutes))


mailer = Mailer()


def send_password_reset_job(to: str, full_name: str, reset_url: str,
                            expires_minutes: int) -> None:
    try:
        mailer.send_password_reset(to, full_name, reset_url, expires_minutes)
    except Exception:
        logger.exception("password reset email failed for %s", to)
