import smtplib
from unittest.mock import MagicMock, patch

import pytest
from app.core.mailer import Mailer, _reset_text, APP_NAME, RESET_SUBJECT


def test_reset_text_plain_format():
    """Ensure plain text version contains full name, reset URL and expiration"""
    text = _reset_text(
        full_name="Pawan Kumar",
        reset_url="http://localhost:3000/reset-password?token=sample",
        expires_minutes=15
    )
    assert "Hi Pawan Kumar" in text
    assert "http://localhost:3000/reset-password?token=sample" in text
    assert "15 minutes" in text
    assert APP_NAME in text


def test_mailer_send_password_reset_renders_template_and_calls_send():
    """Ensure send_password_reset renders HTML template and calls send method"""
    mailer = Mailer()
    with patch.object(mailer, "send") as mock_send:
        mailer.send_password_reset(
            to="user@example.com",
            full_name="Test User",
            reset_url="http://localhost:3000/reset-password?token=xyz",
            expires_minutes=15
        )
        mock_send.assert_called_once()
        args, _ = mock_send.call_args
        to_arg, subject_arg, html_arg, text_arg = args

        assert to_arg == "user@example.com"
        assert subject_arg == RESET_SUBJECT
        assert "Test User" in html_arg
        assert "http://localhost:3000/reset-password?token=xyz" in html_arg
        assert "Test User" in text_arg
