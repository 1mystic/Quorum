import pytest
from unittest.mock import AsyncMock


# ==== fixtures ====

@pytest.fixture
def mock_google_token(monkeypatch):
    """Patches verify_google_id_token to return controllable claims instead of calling Google."""
    def _mock(claims: dict):
        mock_verify = AsyncMock(return_value=claims)
        monkeypatch.setattr("app.services.user.verify_google_id_token", mock_verify)
        return mock_verify
    return _mock


def google_claims(email: str, email_verified: bool = True, sub: str = "google-sub-123"):
    return {
        "email": email,
        "email_verified": email_verified,
        "sub": sub,
        "picture": "https://example.com/photo.jpg",
    }


# ==== 1. happy path ====

@pytest.mark.asyncio
async def test_google_signup_creates_member_for_matching_tenant_domain(client, seed_tenant, mock_google_token):
    """Verify that Google signup with matching tenant domain creates member"""
    mock_google_token(google_claims("newmember@knit.edu.in"))

    payload = {"id_token": "fake-token", "intent": "signup"}
    response = await client.post("/auth/google", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert isinstance(body["access_token"], str)
    assert len(body["access_token"]) > 0
    assert "refresh_token" in body
    assert isinstance(body["refresh_token"], str)
    assert len(body["refresh_token"]) > 0
    assert body["is_new_user"] is True


@pytest.mark.asyncio
async def test_google_login_existing_user_succeeds(client, seed_tenant, mock_google_token):
    """Verify that Google login succeeds for existing user"""
    mock_google_token(google_claims("existing@knit.edu.in"))
    signup_payload = {"id_token": "fake-token", "intent": "signup"}
    await client.post("/auth/google", json=signup_payload)

    login_payload = {"id_token": "fake-token", "intent": "login"}
    response = await client.post("/auth/google", json=login_payload)
    assert response.status_code == 200
    body = response.json()
    assert body["is_new_user"] is False
    assert "access_token" in body
    assert isinstance(body["access_token"], str)
    assert len(body["access_token"]) > 0


@pytest.mark.asyncio
async def test_google_login_links_existing_password_account(client, seed_tenant, mock_google_token):
    """Verify that Google login links password account"""
    signup_payload = {
        "email": "linked@knit.edu.in",
        "full_name": "Linked User",
        "password": "Test@1234",
        "confirm_password": "Test@1234",
        "role": "MEMBER",
    }
    await client.post("/auth/signup", json=signup_payload)

    mock_google_token(google_claims("linked@knit.edu.in"))
    google_payload = {"id_token": "fake-token", "intent": "login"}
    response = await client.post("/auth/google", json=google_payload)
    assert response.status_code == 200
    body = response.json()
    assert body["is_new_user"] is False
    assert "access_token" in body


# ==== 2. validation ====

@pytest.mark.asyncio
async def test_google_auth_missing_id_token_fails(client):
    """Verify that missing ID token fails verification"""
    payload = {"intent": "login"}
    response = await client.post("/auth/google", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_google_auth_invalid_intent_fails(client):
    """Verify that invalid intent fails verification"""
    payload = {"id_token": "fake-token", "intent": "delete_everything"}
    response = await client.post("/auth/google", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_google_auth_empty_payload_fails(client):
    """Verify that empty payload fails verification"""
    payload = {}
    response = await client.post("/auth/google", json=payload)
    assert response.status_code == 422


# ==== 3. business rules ====

# @pytest.mark.asyncio
# async def test_google_signup_without_matching_tenant_creates_tenant_admin(client, mock_google_token):
#     """Verify that Google signup without matching domain creates admin"""
#     mock_google_token(google_claims("randomperson@unknown-domain.com"))

#     payload = {"id_token": "fake-token", "intent": "signup"}
#     response = await client.post("/auth/google", json=payload)
#     assert response.status_code == 200
#     assert response.json()["is_new_user"] is True


@pytest.mark.asyncio
async def test_google_login_with_no_matching_tenant_fails(client, mock_google_token):
    """Verify that Google login with unregistered domain fails"""
    mock_google_token(google_claims("ghost@unknown-domain.com"))

    payload = {"id_token": "fake-token", "intent": "login"}
    response = await client.post("/auth/google", json=payload)
    assert response.status_code == 404
    assert response.json()["message"] == "Tenant not registered"


@pytest.mark.asyncio
async def test_google_login_with_matching_tenant_but_no_account_fails(client, seed_tenant, mock_google_token):
    """Verify that Google login with missing account fails"""
    mock_google_token(google_claims("neveronboarded@knit.edu.in"))

    payload = {"id_token": "fake-token", "intent": "login"}
    response = await client.post("/auth/google", json=payload)
    assert response.status_code == 404
    assert response.json()["message"] == "Account does not exist"


@pytest.mark.asyncio
async def test_google_auth_unverified_email_fails(client, seed_tenant, mock_google_token):
    """Verify that unverified Google email fails verification"""
    mock_google_token(google_claims("unverified@knit.edu.in", email_verified=False))

    payload = {"id_token": "fake-token", "intent": "signup"}
    response = await client.post("/auth/google", json=payload)
    assert response.status_code == 403
    assert response.json()["message"] == "Google account email is not verified"


@pytest.mark.asyncio
async def test_google_auth_invalid_token_fails(client, monkeypatch):
    """Verify that invalid Google token fails verification"""
    from app.exceptions import InvalidGoogleTokenError

    async def _raise(*args, **kwargs):
        raise InvalidGoogleTokenError()

    monkeypatch.setattr("app.services.user.verify_google_id_token", _raise)

    payload = {"id_token": "garbage-token", "intent": "login"}
    response = await client.post("/auth/google", json=payload)
    assert response.status_code == 401


# ==== 4. boundary ====

@pytest.mark.asyncio
async def test_google_signup_subdomain_of_tenant_matches(client, seed_tenant, mock_google_token):
    """Verify that tenant subdomains are matched correctly"""
    mock_google_token(google_claims("newmember@cs.knit.edu.in"))

    payload = {"id_token": "fake-token", "intent": "signup"}
    response = await client.post("/auth/google", json=payload)
    assert response.status_code == 200
    assert response.json()["is_new_user"] is True


@pytest.mark.asyncio
async def test_google_auth_email_case_insensitive_match(client, seed_tenant, mock_google_token):
    """Verify that email matching is case-insensitive"""
    mock_google_token(google_claims("caseuser@knit.edu.in"))
    signup_payload = {"id_token": "fake-token", "intent": "signup"}
    await client.post("/auth/google", json=signup_payload)

    mock_google_token(google_claims("CaseUser@knit.edu.in"))
    login_payload = {"id_token": "fake-token", "intent": "login"}
    response = await client.post("/auth/google", json=login_payload)
    assert response.status_code == 200
    assert response.json()["is_new_user"] is False


# ==== 5. edge cases ====

@pytest.mark.asyncio
async def test_google_signup_twice_with_same_email_treats_second_as_login(client, seed_tenant, mock_google_token):
    """Verify that duplicate signup intent acts as login"""
    mock_google_token(google_claims("repeat@knit.edu.in"))
    first = {"id_token": "fake-token", "intent": "signup"}
    first_response = await client.post("/auth/google", json=first)
    assert first_response.json()["is_new_user"] is True

    second = {"id_token": "fake-token", "intent": "signup"}
    second_response = await client.post("/auth/google", json=second)
    assert second_response.status_code == 200
    assert second_response.json()["is_new_user"] is False
