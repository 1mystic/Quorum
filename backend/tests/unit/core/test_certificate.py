import re
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.certificate import CertificateContext, abbreviate, clip, make_serial, render_pdf
from app.models import RegistrationResult
from app.services.certificate import CertificateService


def test_abbreviate_multi_word_title():
    """Verify that a multi-word title is abbreviated to its first letters"""
    assert abbreviate("Data Science & AI") == "DSA"


def test_abbreviate_single_word_title():
    """Confirm that a single-word title abbreviates to just that word's first letter"""
    assert abbreviate("Hackathon") == "H"


def test_abbreviate_numeric_title_uses_digit():
    """Confirm that a title starting with numbers uses the digit, not EVT fallback"""
    assert abbreviate("12345") == "1"


def test_abbreviate_symbol_only_title_falls_back_to_evt():
    """Ensure that a title with only symbols falls back to the EVT default"""
    assert abbreviate("---") == "EVT"
    assert abbreviate("!!! @@@ ###") == "EVT"


def test_abbreviate_special_characters_are_stripped():
    """Confirm that punctuation and symbols don't break abbreviation"""
    result = abbreviate("C++ & Python: Workshop #1")
    assert result.isalpha()
    assert len(result) <= 3


def test_make_serial_format():
    """Verify that a generated serial matches the expected CC-XXX-YYYY-NNNNN pattern"""
    serial = make_serial("Robotics Workshop", datetime(2026, 8, 9))
    assert re.match(r"^CC-RW-2026-\d{5}$", serial)


def test_make_serial_symbol_title_uses_evt_prefix():
    """Confirm that a purely symbol event title falls back to EVT prefix"""
    serial = make_serial("---", datetime(2026, 8, 9))
    assert re.match(r"^CC-EVT-2026-\d{5}$", serial)


def test_clip_truncates_long_text():
    """Verify that text longer than the limit is truncated with an ellipsis"""
    result = clip("Very long string that exceeds the limit", 10)
    assert result == "Very long…"
    assert len(result) == 10


def test_clip_leaves_short_text_unchanged():
    """Confirm that text within the limit is returned unmodified"""
    assert clip("Short", 10) == "Short"


def test_clip_exact_length_unchanged():
    """Confirm that text exactly at the limit is not truncated"""
    text = "Exactly10!"
    assert len(text) == 10
    assert clip(text, 10) == text


@pytest.mark.parametrize("result", [
    RegistrationResult.WINNER,
    RegistrationResult.RUNNER_UP,
    RegistrationResult.PARTICIPANT,
])
def test_render_pdf_all_result_templates(result):
    """Verify that all three certificate templates render without error"""
    context = CertificateContext(
        serial="CC-TEST-2026-00001",
        result=result,
        member_name="Test Member",
        event_title="Test Event",
        event_date=datetime.now(timezone.utc),
        group_name="Test Group",
        tenant_name="Test University",
        signatory_name="Test Signatory",
        signatory_role="Group President",
    )
    pdf_bytes = render_pdf(context)
    assert pdf_bytes[:4] == b"%PDF"


def test_render_pdf_handles_long_member_name():
    """Confirm that a very long member name doesn't crash PDF rendering"""
    context = CertificateContext(
        serial="CC-TEST-2026-00001",
        result=RegistrationResult.WINNER,
        member_name="A" * 60,
        event_title="B" * 60,
        event_date=datetime.now(timezone.utc),
        group_name="Test Group",
        tenant_name="Test University",
        signatory_name="Test Signatory",
        signatory_role="Group President",
    )
    pdf_bytes = render_pdf(context)
    assert pdf_bytes.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_reserve_serial_exhausts_attempts_raises_error():
    """Confirm that exhausting all serial retry attempts raises RuntimeError"""
    certificate_repo = AsyncMock()
    certificate_repo.serial_exists.return_value = True  # always collides

    service = CertificateService(
        certificate_repo=certificate_repo,
        member_repo=AsyncMock(),
        notification_repo=AsyncMock(),
        storage=AsyncMock(),
    )

    with pytest.raises(RuntimeError, match="could not find a free serial"):
        await service._reserve_serial("Test Event", datetime.now(timezone.utc))


@pytest.mark.asyncio
async def test_request_skips_non_checked_in_registration():
    """Confirm that request() returns None for a registration that was never checked in"""
    registration = MagicMock(checked_in=False, result=RegistrationResult.PARTICIPANT)
    event = MagicMock()
    group = MagicMock()
    tenant = MagicMock()

    certificate_repo = AsyncMock()
    certificate_repo.issue_context.return_value = (
        registration, event, group, tenant, "Test Member", "Test Signatory"
    )

    service = CertificateService(
        certificate_repo=certificate_repo,
        member_repo=AsyncMock(),
        notification_repo=AsyncMock(),
        storage=AsyncMock(),
    )
    result = await service.request(registration_id=1)
    assert result is None


@pytest.mark.asyncio
async def test_request_skips_registrant_result():
    """Confirm that request() returns None when checked in but result is still REGISTRANT"""
    registration = MagicMock(checked_in=True, result=RegistrationResult.REGISTRANT)
    event = MagicMock()
    group = MagicMock()
    tenant = MagicMock()

    certificate_repo = AsyncMock()
    certificate_repo.issue_context.return_value = (
        registration, event, group, tenant, "Test Member", "Test Signatory"
    )

    service = CertificateService(
        certificate_repo=certificate_repo,
        member_repo=AsyncMock(),
        notification_repo=AsyncMock(),
        storage=AsyncMock(),
    )
    result = await service.request(registration_id=1)
    assert result is None


@pytest.mark.asyncio
async def test_request_skips_missing_registration():
    """Confirm that request() returns None when the registration ID doesn't exist"""
    certificate_repo = AsyncMock()
    certificate_repo.issue_context.return_value = None

    service = CertificateService(
        certificate_repo=certificate_repo,
        member_repo=AsyncMock(),
        notification_repo=AsyncMock(),
        storage=AsyncMock(),
    )
    result = await service.request(registration_id=99999)
    assert result is None
