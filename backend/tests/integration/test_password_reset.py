import httpx
import pytest
from sqlalchemy import select

from app.core.token import create_reset_token, create_access_token, create_refresh_token
from app.utils.hashing import password_fingerprint
from app.models.user import User

MAILHOG_API_BASE = "http://localhost:8025/api"


@pytest.mark.asyncio
async def test_forgot_password_registered_email_sends_mail(client, seed_tenant, clear_mailhog):
    """Verify that a password reset email is sent via MailHog for a registered email"""
    payload = {
        "email": "forgot.test@knit.edu.in",
        "full_name": "Forgot Test User",
        "password": "Forgot@123",
        "confirm_password": "Forgot@123",
        "role": "MEMBER"
    }
    await client.post("/auth/signup", json=payload)

    payload = {"email": "forgot.test@knit.edu.in"}
    response = await client.post("/auth/forgot-password", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "If that email is registered, a password reset link has been sent to it"

    mailhog_response = httpx.get(f"{MAILHOG_API_BASE}/v2/messages")
    messages = mailhog_response.json()["items"]
    assert len(messages) == 1
    assert "forgot.test@knit.edu.in" in messages[0]["Raw"]["To"][0]


@pytest.mark.asyncio
async def test_forgot_password_unregistered_email_returns_same_message(client, clear_mailhog):
    """Verify that forgot-password returns the same generic message for an unregistered email"""
    payload = {"email": "ghost.reset@knit.edu.in"}
    response = await client.post("/auth/forgot-password", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "If that email is registered, a password reset link has been sent to it"

    mailhog_response = httpx.get(f"{MAILHOG_API_BASE}/v2/messages")
    assert len(mailhog_response.json()["items"]) == 0


@pytest.mark.asyncio
async def test_forgot_password_invalid_email_format_fails(client):
    """Validate that forgot-password is rejected when the email is malformed"""
    payload = {"email": "not-an-email"}
    response = await client.post("/auth/forgot-password", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_forgot_password_missing_email_field_fails(client):
    """Validate that forgot-password is rejected when the email field is missing"""
    payload = {}
    response = await client.post("/auth/forgot-password", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_reset_password_success_flow(client, seed_tenant, db_session):
    """Verify that reset-password updates the password and login works with the new password"""
    signup_payload = {
        "email": "reset.flow@knit.edu.in",
        "full_name": "Reset Flow User",
        "password": "OldPass@123",
        "confirm_password": "OldPass@123",
        "role": "MEMBER"
    }
    await client.post("/auth/signup", json=signup_payload)

    result = await db_session.execute(select(User).where(User.email == signup_payload["email"]))
    user = result.scalar_one()

    reset_token = create_reset_token(
        payload={
            "sub": str(user.id),
            "email": user.email,
            "pwd": password_fingerprint(user.hashed_password),
        }
    )

    reset_payload = {
        "token": reset_token,
        "password": "NewPass@456",
        "confirm_password": "NewPass@456"
    }
    reset_response = await client.post("/auth/reset-password", json=reset_payload)
    assert reset_response.status_code == 200
    body = reset_response.json()
    assert body["message"] == "Password reset successfully, please log in with your new password"

    new_login_payload = {
        "email": signup_payload["email"],
        "password": "NewPass@456"
    }
    new_login = await client.post("/auth/login", json=new_login_payload)
    assert new_login.status_code == 200
    assert "access_token" in new_login.json()

    old_login_payload = {
        "email": signup_payload["email"],
        "password": "OldPass@123"
    }
    old_login = await client.post("/auth/login", json=old_login_payload)
    assert old_login.status_code == 401
    assert old_login.json()["message"] == "Incorrect email or password"


@pytest.mark.asyncio
async def test_reset_password_token_single_use_fails_on_replay(client, seed_tenant, db_session):
    """Verify that a reset token cannot be reused after the password has already been reset"""
    signup_payload = {
        "email": "replay.test@knit.edu.in",
        "full_name": "Replay Test User",
        "password": "OldPass@123",
        "confirm_password": "OldPass@123",
        "role": "MEMBER"
    }
    await client.post("/auth/signup", json=signup_payload)

    result = await db_session.execute(select(User).where(User.email == signup_payload["email"]))
    user = result.scalar_one()

    reset_token = create_reset_token(
        payload={
            "sub": str(user.id),
            "email": user.email,
            "pwd": password_fingerprint(user.hashed_password),
        }
    )

    first_response = await client.post("/auth/reset-password", json={
        "token": reset_token,
        "password": "NewPass@456",
        "confirm_password": "NewPass@456"
    })
    assert first_response.status_code == 200

    second_response = await client.post("/auth/reset-password", json={
        "token": reset_token,
        "password": "AnotherPass@789",
        "confirm_password": "AnotherPass@789"
    })
    assert second_response.status_code == 401
    assert second_response.json()["message"] == "Invalid token"


@pytest.mark.asyncio
async def test_reset_password_expired_token_fails(client, seed_tenant, db_session):
    """Verify that an expired reset token is rejected"""
    signup_payload = {
        "email": "expired.test@knit.edu.in",
        "full_name": "Expired Test User",
        "password": "OldPass@123",
        "confirm_password": "OldPass@123",
        "role": "MEMBER"
    }
    await client.post("/auth/signup", json=signup_payload)

    result = await db_session.execute(select(User).where(User.email == signup_payload["email"]))
    user = result.scalar_one()

    expired_token = create_reset_token(
        payload={
            "sub": str(user.id),
            "email": user.email,
            "pwd": password_fingerprint(user.hashed_password),
        },
        expires_minutes=-1
    )

    response = await client.post("/auth/reset-password", json={
        "token": expired_token,
        "password": "NewPass@456",
        "confirm_password": "NewPass@456"
    })
    assert response.status_code == 401
    assert response.json()["message"] == "Invalid token"


@pytest.mark.asyncio
async def test_reset_password_access_token_rejected(client, seed_tenant):
    """Verify that a regular access token cannot be used as a reset token"""
    signup_payload = {
        "email": "wrongtype.test@knit.edu.in",
        "full_name": "Wrong Type Test User",
        "password": "OldPass@123",
        "confirm_password": "OldPass@123",
        "role": "MEMBER"
    }
    signup_response = await client.post("/auth/signup", json=signup_payload)
    access_token = signup_response.json()["access_token"]

    response = await client.post("/auth/reset-password", json={
        "token": access_token,
        "password": "NewPass@456",
        "confirm_password": "NewPass@456"
    })
    assert response.status_code == 401
    assert response.json()["message"] == "Invalid token"


@pytest.mark.asyncio
async def test_reset_password_refresh_token_rejected(client, seed_tenant):
    """Verify that a refresh token cannot be used as a reset token"""
    signup_payload = {
        "email": "refreshtype.test@knit.edu.in",
        "full_name": "Refresh Type Test User",
        "password": "OldPass@123",
        "confirm_password": "OldPass@123",
        "role": "MEMBER"
    }
    signup_response = await client.post("/auth/signup", json=signup_payload)
    refresh_token = signup_response.json()["refresh_token"]

    response = await client.post("/auth/reset-password", json={
        "token": refresh_token,
        "password": "NewPass@456",
        "confirm_password": "NewPass@456"
    })
    assert response.status_code == 401
    assert response.json()["message"] == "Invalid token"


@pytest.mark.asyncio
async def test_reset_password_malformed_token_rejected(client):
    """Verify that a malformed or tampered token string is rejected"""
    response = await client.post("/auth/reset-password", json={
        "token": "this.is.not-a-valid-jwt",
        "password": "NewPass@456",
        "confirm_password": "NewPass@456"
    })
    assert response.status_code == 401
    assert response.json()["message"] == "Invalid token"


@pytest.mark.asyncio
async def test_reset_password_confirm_mismatch_fails(client, seed_tenant, db_session):
    """Validate that reset-password is rejected when password and confirm_password do not match"""
    signup_payload = {
        "email": "mismatch.test@knit.edu.in",
        "full_name": "Mismatch Test User",
        "password": "OldPass@123",
        "confirm_password": "OldPass@123",
        "role": "MEMBER"
    }
    await client.post("/auth/signup", json=signup_payload)

    result = await db_session.execute(select(User).where(User.email == signup_payload["email"]))
    user = result.scalar_one()

    reset_token = create_reset_token(
        payload={
            "sub": str(user.id),
            "email": user.email,
            "pwd": password_fingerprint(user.hashed_password),
        }
    )

    response = await client.post("/auth/reset-password", json={
        "token": reset_token,
        "password": "NewPass@456",
        "confirm_password": "Different@789"
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_reset_password_short_password_fails(client, seed_tenant, db_session):
    """Validate that reset-password is rejected when the new password is below the minimum length"""
    signup_payload = {
        "email": "shortpass.test@knit.edu.in",
        "full_name": "Short Pass Test User",
        "password": "OldPass@123",
        "confirm_password": "OldPass@123",
        "role": "MEMBER"
    }
    await client.post("/auth/signup", json=signup_payload)

    result = await db_session.execute(select(User).where(User.email == signup_payload["email"]))
    user = result.scalar_one()

    reset_token = create_reset_token(
        payload={
            "sub": str(user.id),
            "email": user.email,
            "pwd": password_fingerprint(user.hashed_password),
        }
    )

    response = await client.post("/auth/reset-password", json={
        "token": reset_token,
        "password": "short1",
        "confirm_password": "short1"
    })
    assert response.status_code == 422
