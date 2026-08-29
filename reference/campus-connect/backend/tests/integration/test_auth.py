import pytest

# ==== signup ====

@pytest.mark.asyncio
async def test_signup_success(client, seed_college):
    """Verify that student signup succeeds when a matching college exists for the email domain"""
    payload = {
        "email": "pawan.kumar@knit.edu.in",
        "full_name": "Pawan Kumar",
        "password": "Pawan@123",
        "confirm_password": "Pawan@123",
        "role": "STUDENT"
    }
    response = await client.post("/auth/signup", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert isinstance(body["access_token"], str)
    assert len(body["access_token"]) > 0
    assert "refresh_token" in body
    assert isinstance(body["refresh_token"], str)
    assert len(body["refresh_token"]) > 0
    assert body["message"] == "Account created successfully"


@pytest.mark.asyncio
async def test_signup_admin_success_new_college(client):
    """Verify that admin signup succeeds when no college exists for the email domain"""
    payload = {
        "email": "admin@newcollege.edu",
        "full_name": "Admin User",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "CAMPUS_ADMIN"
    }
    response = await client.post("/auth/signup", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert isinstance(body["access_token"], str)
    assert len(body["access_token"]) > 0
    assert "refresh_token" in body
    assert isinstance(body["refresh_token"], str)
    assert len(body["refresh_token"]) > 0
    assert body["message"] == "Account created successfully"


@pytest.mark.asyncio
async def test_signup_subdomain_of_college_matches(client, seed_college):
    """Verify that signup succeeds when the email is a subdomain of an existing college"""
    payload = {
        "email": "student@cs.knit.edu.in",
        "full_name": "Subdomain Student",
        "password": "Test@1234",
        "confirm_password": "Test@1234",
        "role": "STUDENT"
    }
    response = await client.post("/auth/signup", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert isinstance(body["access_token"], str)
    assert len(body["access_token"]) > 0
    assert "refresh_token" in body
    assert isinstance(body["refresh_token"], str)
    assert len(body["refresh_token"]) > 0
    assert body["message"] == "Account created successfully"


@pytest.mark.asyncio
async def test_signup_email_case_insensitive_login(client, seed_college):
    """Verify that signing up with an uppercase email allows subsequent login with the lowercase email"""
    payload = {
        "email": "Pawan.Kumar@knit.edu.in",
        "full_name": "Pawan Kumar",
        "password": "Pawan@123",
        "confirm_password": "Pawan@123",
        "role": "STUDENT"
    }
    signup_response = await client.post("/auth/signup", json=payload)
    assert signup_response.status_code == 200

    payload = {
        "email": "pawan.kumar@knit.edu.in",
        "password": "Pawan@123"
    }
    response = await client.post("/auth/login", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert isinstance(body["access_token"], str)
    assert len(body["access_token"]) > 0
    assert "refresh_token" in body
    assert isinstance(body["refresh_token"], str)
    assert len(body["refresh_token"]) > 0
    assert body["message"] == "Logged in successfully"


@pytest.mark.asyncio
async def test_signup_max_length_name_succeeds(client, seed_college):
    """Validate that signup succeeds with a full name exactly at the 100-character limit"""
    payload = {
        "email": "longname@knit.edu.in",
        "full_name": "A" * 100,
        "password": "Test@1234",
        "confirm_password": "Test@1234",
        "role": "STUDENT"
    }
    response = await client.post("/auth/signup", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert isinstance(body["access_token"], str)
    assert len(body["access_token"]) > 0
    assert "refresh_token" in body
    assert isinstance(body["refresh_token"], str)
    assert len(body["refresh_token"]) > 0
    assert body["message"] == "Account created successfully"


@pytest.mark.asyncio
async def test_signup_student_without_college_fails(client):
    """Verify that student signup is rejected when no matching college exists for the email domain"""
    payload = {
        "email": "someone@unknown-domain.edu",
        "full_name": "Someone Unknown",
        "password": "Test@1234",
        "confirm_password": "Test@1234",
        "role": "STUDENT"
    }
    response = await client.post("/auth/signup", json=payload)
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "College not registered"


@pytest.mark.asyncio
async def test_signup_duplicate_email_fails(client, seed_college):
    """Verify that signup is rejected when the email is already registered"""
    payload = {
        "email": "rohit.mehta@knit.edu.in",
        "full_name": "Rohit Mehta",
        "password": "Rohit@123",
        "confirm_password": "Rohit@123",
        "role": "STUDENT"
    }
    await client.post("/auth/signup", json=payload)
    response = await client.post("/auth/signup", json=payload)
    assert response.status_code == 409
    body = response.json()
    assert body["message"] == "Email already registered"


@pytest.mark.asyncio
async def test_signup_campus_admin_with_existing_college_fails(client, seed_college):
    """Verify that admin signup is rejected if a college already exists for that domain"""
    payload = {
        "email": "admin.office@knit.edu.in",
        "full_name": "Admin Office",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "CAMPUS_ADMIN"
    }
    response = await client.post("/auth/signup", json=payload)
    assert response.status_code == 409
    body = response.json()
    assert body["message"] == "College already registered"


@pytest.mark.asyncio
async def test_signup_password_mismatch_fails(client, seed_college):
    """Validate that signup is rejected when password and confirm password do not match"""
    payload = {
        "email": "amit.verma@knit.edu.in",
        "full_name": "Amit Verma",
        "password": "Amit@123",
        "confirm_password": "Different@123",
        "role": "STUDENT"
    }
    response = await client.post("/auth/signup", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_signup_invalid_email_fails(client):
    """Validate that signup is rejected when the email is malformed"""
    payload = {
        "email": "not-an-email",
        "full_name": "Vikram Singh",
        "password": "Vikram@123",
        "confirm_password": "Vikram@123",
        "role": "STUDENT"
    }
    response = await client.post("/auth/signup", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_signup_short_name_fails(client):
    """Validate that signup is rejected when the full name is below the minimum length"""
    payload = {
        "email": "raj.patel@knit.edu.in",
        "full_name": "Raj",
        "password": "Raj@12345",
        "confirm_password": "Raj@12345",
        "role": "STUDENT"
    }
    response = await client.post("/auth/signup", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_signup_short_password_fails(client):
    """Validate that signup is rejected when the password is below the minimum length"""
    payload = {
        "email": "suresh.rao@knit.edu.in",
        "full_name": "Suresh Rao",
        "password": "abc123",
        "confirm_password": "abc123",
        "role": "STUDENT"
    }
    response = await client.post("/auth/signup", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_signup_missing_fields_fails(client):
    """Validate that signup is rejected when required fields are missing"""
    payload = {
        "email": "karan.gupta@knit.edu.in",
        "password": "Karan@123"
    }
    response = await client.post("/auth/signup", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_signup_empty_payload_fails(client):
    """Validate that signup is rejected when the request body is empty"""
    payload = {}
    response = await client.post("/auth/signup", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_signup_invalid_role_fails(client):
    """Validate that signup is rejected when the role value is invalid"""
    payload = {
        "email": "someone@knit.edu.in",
        "full_name": "Someone Random",
        "password": "Test@1234",
        "confirm_password": "Test@1234",
        "role": "SUPERUSER"
    }
    response = await client.post("/auth/signup", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_signup_name_with_only_whitespace_fails(client, seed_college):
    """Validate that signup is rejected when the full name consists only of whitespace"""
    payload = {
        "email": "blankname@knit.edu.in",
        "full_name": "     ",
        "password": "Test@1234",
        "confirm_password": "Test@1234",
        "role": "STUDENT"
    }
    response = await client.post("/auth/signup", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_signup_over_max_length_name_fails(client):
    """Validate that signup is rejected when the full name exceeds the 100-character limit"""
    payload = {
        "email": "toolongname@knit.edu.in",
        "full_name": "A" * 101,
        "password": "Test@1234",
        "confirm_password": "Test@1234",
        "role": "STUDENT"
    }
    response = await client.post("/auth/signup", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_signup_over_max_length_password_fails(client):
    """Validate that signup is rejected when the password exceeds the 255-character limit"""
    payload = {
        "email": "longpass@knit.edu.in",
        "full_name": "Long Pass User",
        "password": "A" * 256,
        "confirm_password": "A" * 256,
        "role": "STUDENT"
    }
    response = await client.post("/auth/signup", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_signup_password_whitespace_mismatch_fails(client, seed_college):
    """Validate that signup is rejected when password and confirm password differ by trailing whitespace"""
    payload = {
        "email": "whitespace.test@knit.edu.in",
        "full_name": "Whitespace Test User",
        "password": "Test@123",
        "confirm_password": "Test@123 ",
        "role": "STUDENT"
    }
    response = await client.post("/auth/signup", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_signup_login_special_characters_password(client, seed_college):
    """Confirm that signup and login succeed with a password containing special characters and emojis"""
    payload = {
        "email": "emoji.test@knit.edu.in",
        "full_name": "Emoji Test User",
        "password": "P@ss w0rd! 🔥",
        "confirm_password": "P@ss w0rd! 🔥",
        "role": "STUDENT"
    }
    signup_response = await client.post("/auth/signup", json=payload)
    assert signup_response.status_code == 200
    
    login_payload = {
        "email": "emoji.test@knit.edu.in",
        "password": "P@ss w0rd! 🔥"
    }
    response = await client.post("/auth/login", json=login_payload)
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert isinstance(body["access_token"], str)
    assert len(body["access_token"]) > 0
    assert body["message"] == "Logged in successfully"


# ==== login ====

@pytest.mark.asyncio
async def test_login_success(client, seed_college):
    """Verify that login succeeds with the correct email and password"""
    payload = {
        "email": "manoj.tiwari@knit.edu.in",
        "full_name": "Manoj Tiwari",
        "password": "Manoj@123",
        "confirm_password": "Manoj@123",
        "role": "STUDENT"
    }
    await client.post("/auth/signup", json=payload)

    payload = {
        "email": "manoj.tiwari@knit.edu.in",
        "password": "Manoj@123"
    }
    response = await client.post("/auth/login", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert isinstance(body["access_token"], str)
    assert len(body["access_token"]) > 0
    assert "refresh_token" in body
    assert isinstance(body["refresh_token"], str)
    assert len(body["refresh_token"]) > 0
    assert body["message"] == "Logged in successfully"


@pytest.mark.asyncio
async def test_login_admin_success(client):
    """Verify that admin login succeeds with the correct email and password"""
    payload = {
        "email": "admin.login@newcollege.edu",
        "full_name": "Admin Login User",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "CAMPUS_ADMIN"
    }
    await client.post("/auth/signup", json=payload)

    payload = {
        "email": "admin.login@newcollege.edu",
        "password": "Admin@123"
    }
    response = await client.post("/auth/login", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert isinstance(body["access_token"], str)
    assert len(body["access_token"]) > 0
    assert "refresh_token" in body
    assert isinstance(body["refresh_token"], str)
    assert len(body["refresh_token"]) > 0
    assert body["message"] == "Logged in successfully"


@pytest.mark.asyncio
async def test_login_wrong_password_fails(client, seed_college):
    """Verify that login is rejected when the password is incorrect"""
    payload = {
        "email": "deepak.yadav@knit.edu.in",
        "full_name": "Deepak Yadav",
        "password": "Deepak@123",
        "confirm_password": "Deepak@123",
        "role": "STUDENT"
    }
    await client.post("/auth/signup", json=payload)

    payload = {
        "email": "deepak.yadav@knit.edu.in",
        "password": "WrongPass1"
    }
    response = await client.post("/auth/login", json=payload)
    assert response.status_code == 401
    body = response.json()
    assert body["message"] == "Incorrect email or password"


@pytest.mark.asyncio
async def test_login_nonexistent_user_fails(client):
    """Verify that login is rejected when the email is not registered"""
    payload = {
        "email": "ghost.user@knit.edu.in",
        "password": "Test@1234"
    }
    response = await client.post("/auth/login", json=payload)
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "College not registered"


@pytest.mark.asyncio
async def test_login_short_password_fails(client, seed_college):
    """Validate that login is rejected when the password is below the minimum length"""
    payload = {
        "email": "shortpasslogin@knit.edu.in",
        "password": "ab"
    }
    response = await client.post("/auth/login", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_missing_password_field_fails(client):
    """Validate that login is rejected when the password field is missing"""
    payload = {
        "email": "missingpass@knit.edu.in"
    }
    response = await client.post("/auth/login", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_password_case_sensitive(client, seed_college):
    """Verify that login is rejected when the password casing is incorrect"""
    payload = {
        "email": "casing.test@knit.edu.in",
        "full_name": "Casing Test User",
        "password": "SecretP@ss",
        "confirm_password": "SecretP@ss",
        "role": "STUDENT"
    }
    await client.post("/auth/signup", json=payload)

    login_payload = {
        "email": "casing.test@knit.edu.in",
        "password": "secretp@ss"
    }
    response = await client.post("/auth/login", json=login_payload)
    assert response.status_code == 401
    body = response.json()
    assert body["message"] == "Incorrect email or password"