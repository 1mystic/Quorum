import pytest


@pytest.mark.asyncio
async def test_onboarding_success(client, admin_token):
    """Verify that tenant onboarding succeeds for an admin with a valid token"""
    payload = {
        "name": "Kamla Nehru Institute of Technology",
        "email_suffix": "knit.edu.in",
        "description": "Kamla Nehru Institute of Technology"
    }
    response = await client.post(
        "/tenant/onboarding",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == "knit"
    assert body["email_suffix"] == "knit.edu.in"
    assert body["message"] == "Tenant onboarded successfully"


@pytest.mark.asyncio
async def test_onboarding_without_token_fails(client):
    """Verify that tenant onboarding is rejected when no authentication token is provided"""
    payload = {
        "name": "Kamla Nehru Institute of Technology",
        "email_suffix": "knit.edu.in",
        "description": "Kamla Nehru Institute of Technology"
    }
    response = await client.post("/tenant/onboarding", json=payload)
    assert response.status_code == 401
    body = response.json()
    # assert body["message"] == "Not authenticated"
    assert body["detail"] == "Not authenticated"



@pytest.mark.asyncio
async def test_onboarding_with_member_token_fails(client):
    """Verify that tenant onboarding is rejected for a user with the member role"""
    admin_payload = {
        "email": "seed.admin@sometenant.edu",
        "full_name": "Seed Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "TENANT_ADMIN"
    }
    admin_signup = await client.post("/auth/signup", json=admin_payload)
    seed_admin_token = admin_signup.json()["access_token"]

    tenant_payload = {
        "name": "Some Tenant Institute",
        "email_suffix": "sometenant.edu",
        "description": "Just to create a member for this test"
    }
    await client.post(
        "/tenant/onboarding",
        json=tenant_payload,
        headers={"Authorization": f"Bearer {seed_admin_token}"}
    )

    member_payload = {
        "email": "pupil@sometenant.edu",
        "full_name": "Pupil Member",
        "password": "Pupil@123",
        "confirm_password": "Pupil@123",
        "role": "MEMBER"
    }
    member_signup = await client.post("/auth/signup", json=member_payload)
    member_token = member_signup.json()["access_token"]

    onboarding_payload = {
        "name": "Another Tenant Institute",
        "email_suffix": "another.edu",
        "description": "A member should not be able to do this"
    }
    response = await client.post(
        "/tenant/onboarding",
        json=onboarding_payload,
        headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 401
    body = response.json()
    assert body["message"] == "Invalid token"


@pytest.mark.asyncio
async def test_onboarding_duplicate_tenant_fails(client, admin_token):
    """Verify that tenant onboarding is rejected when the tenant already exists"""
    tenant_payload = {
        "name": "Kamla Nehru Institute of Technology",
        "email_suffix": "knit.edu.in",
        "description": "Kamla Nehru Institute of Technology"
    }
    await client.post(
        "/tenant/onboarding",
        json=tenant_payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    admin_payload = {
        "email": "second.admin@differentdomain.edu",
        "full_name": "Second Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "TENANT_ADMIN"
    }
    second_admin = await client.post("/auth/signup", json=admin_payload)
    second_token = second_admin.json()["access_token"]

    response = await client.post(
        "/tenant/onboarding",
        json=tenant_payload,
        headers={"Authorization": f"Bearer {second_token}"}
    )
    assert response.status_code == 409
    body = response.json()
    assert body["message"] == "Tenant already registered"


@pytest.mark.asyncio
async def test_onboarding_missing_fields_fails(client, admin_token):
    """Validate that tenant onboarding is rejected when required fields are missing"""
    payload = {"name": "Kamla Nehru Institute of Technology"}
    response = await client.post(
        "/tenant/onboarding",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_onboarding_invalid_token_fails(client):
    """Verify that tenant onboarding is rejected when an invalid token is provided"""
    payload = {
        "name": "Kamla Nehru Institute of Technology",
        "email_suffix": "knit.edu.in",
        "description": "Kamla Nehru Institute of Technology"
    }
    response = await client.post(
        "/tenant/onboarding",
        json=payload,
        headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401
    body = response.json()
    assert body["message"] == "Invalid token"


@pytest.mark.asyncio
async def test_onboarding_short_name_fails(client, admin_token):
    """Validate that tenant onboarding is rejected when the tenant name is below the minimum length"""
    payload = {
        "name": "KN",
        "email_suffix": "shortname.edu.in",
        "description": "Name is too short here"
    }
    response = await client.post(
        "/tenant/onboarding",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_onboarding_short_description_fails(client, admin_token):
    """Validate that tenant onboarding is rejected when the tenant description is below the minimum length"""
    payload = {
        "name": "Kamla Nehru Institute of Technology",
        "email_suffix": "shortdesc.edu.in",
        "description": "Hi"
    }
    response = await client.post(
        "/tenant/onboarding",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_onboarding_slug_collision_increments(client, admin_token):
    """Verify that tenant onboarding generates an incremented numeric suffix for the slug when a prefix collision occurs"""
    first_payload = {
        "name": "Kamla Nehru Institute of Technology",
        "email_suffix": "knit.edu.in",
        "description": "First tenant with this slug prefix"
    }
    await client.post(
        "/tenant/onboarding",
        json=first_payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    admin_payload = {
        "email": "second.admin@knit.org.in",
        "full_name": "Second Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "TENANT_ADMIN"
    }
    second_admin = await client.post("/auth/signup", json=admin_payload)
    second_token = second_admin.json()["access_token"]

    second_payload = {
        "name": "Kamla Nehru Institute Org",
        "email_suffix": "knit.org.in",
        "description": "Second tenant with colliding slug prefix"
    }
    response = await client.post(
        "/tenant/onboarding",
        json=second_payload,
        headers={"Authorization": f"Bearer {second_token}"}
    )
    assert response.status_code == 200
    assert response.json()["slug"] == "knit-2"
    assert response.json()["message"] == "Tenant onboarded successfully"

@pytest.mark.asyncio
async def test_onboarding_third_slug_collision_increments_further(client, admin_token):
    """Verify that tenant onboarding generates further incremented slug suffixes for subsequent prefix collisions"""
    first_payload = {
        "name": "Kamla Nehru Institute of Technology",
        "email_suffix": "knit.edu.in",
        "description": "First tenant with this slug prefix"
    }
    await client.post(
        "/tenant/onboarding",
        json=first_payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    admin_payload_two = {
        "email": "second.admin@knit.org.in",
        "full_name": "Second Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "TENANT_ADMIN"
    }
    second_admin = await client.post("/auth/signup", json=admin_payload_two)
    second_token = second_admin.json()["access_token"]

    second_payload = {
        "name": "Kamla Nehru Institute Org",
        "email_suffix": "knit.org.in",
        "description": "Second tenant with colliding slug prefix"
    }
    await client.post(
        "/tenant/onboarding",
        json=second_payload,
        headers={"Authorization": f"Bearer {second_token}"}
    )

    admin_payload_three = {
        "email": "third.admin@knit.ac.in",
        "full_name": "Third Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "TENANT_ADMIN"
    }
    third_admin = await client.post("/auth/signup", json=admin_payload_three)
    third_token = third_admin.json()["access_token"]

    third_payload = {
        "name": "Kamla Nehru Institute AC",
        "email_suffix": "knit.ac.in",
        "description": "Third tenant with colliding slug prefix"
    }
    response = await client.post(
        "/tenant/onboarding",
        json=third_payload,
        headers={"Authorization": f"Bearer {third_token}"}
    )
    assert response.status_code == 200
    assert response.json()["slug"] == "knit-3"
    assert response.json()["message"] == "Tenant onboarded successfully"

# ====jul 26=====

@pytest.mark.asyncio
async def test_onboarding_email_suffix_below_min_length_fails(client, admin_token):
    """Validate that tenant onboarding is rejected when the email suffix is below the minimum length"""
    payload = {
        "name": "Kamla Nehru Institute of Technology",
        "email_suffix": "ab",
        "description": "Testing email suffix under minimum length"
    }
    response = await client.post(
        "/tenant/onboarding",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_onboarding_malformed_email_suffix_fails(client, admin_token):
    """Validate that tenant onboarding is rejected when the email suffix is not a valid domain format"""
    payload = {
        "name": "Some Random Tenant",
        "email_suffix": "not_a_domain",
        "description": "Testing malformed suffix"
    }
    response = await client.post(
        "/tenant/onboarding",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code in (400, 422)


@pytest.mark.asyncio
async def test_onboarding_name_over_max_length_fails(client, admin_token):
    """Validate that tenant onboarding is rejected when the tenant name exceeds the maximum length"""
    payload = {
        "name": "A" * 101,
        "email_suffix": "toolongname.edu.in",
        "description": "Testing name over max length"
    }
    response = await client.post(
        "/tenant/onboarding",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_onboarding_description_over_max_length_fails(client, admin_token):
    """Validate that tenant onboarding is rejected when the description exceeds the maximum length"""
    payload = {
        "name": "Kamla Nehru Institute of Technology",
        "email_suffix": "toolongdesc.edu.in",
        "description": "A" * 1001
    }
    response = await client.post(
        "/tenant/onboarding",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_onboarding_email_suffix_over_max_length_fails(client, admin_token):
    """Validate that tenant onboarding is rejected when the email suffix exceeds the maximum length"""
    payload = {
        "name": "Kamla Nehru Institute of Technology",
        "email_suffix": "a" * 101,
        "description": "Testing email suffix over max length"
    }
    response = await client.post(
        "/tenant/onboarding",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_onboarding_whitespace_only_name_fails(client, admin_token):
    """Validate that tenant onboarding is rejected when the tenant name consists only of whitespace"""
    payload = {
        "name": "     ",
        "email_suffix": "blankname.edu.in",
        "description": "Testing whitespace-only name"
    }
    response = await client.post(
        "/tenant/onboarding",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_onboarding_whitespace_only_description_fails(client, admin_token):
    """Validate that tenant onboarding is rejected when the description consists only of whitespace"""
    payload = {
        "name": "Kamla Nehru Institute of Technology",
        "email_suffix": "blankdesc.edu.in",
        "description": "     "
    }
    response = await client.post(
        "/tenant/onboarding",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_onboarding_email_suffix_whitespace_is_stripped(client, admin_token):
    """Verify that leading and trailing whitespace in the email suffix is stripped during onboarding"""
    payload = {
        "name": "Kamla Nehru Institute of Technology",
        "email_suffix": " knit.edu.in ",
        "description": "Testing whitespace stripping on email suffix"
    }
    response = await client.post(
        "/tenant/onboarding",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Kamla Nehru Institute of Technology"
    assert body["slug"] == "knit"
    assert body["email_suffix"] == "knit.edu.in"
    assert body["description"] == "Testing whitespace stripping on email suffix"
    assert isinstance(body["slug"], str)
    assert len(body["slug"]) > 0
    assert body["message"] == "Tenant onboarded successfully"


@pytest.mark.asyncio
async def test_onboarding_suffix_starting_with_dot_fails(client, admin_token):
    """Validate that tenant onboarding is rejected when the email suffix starts with a dot"""
    payload = {
        "name": "Kamla Nehru Institute of Technology",
        "email_suffix": ".knit.edu.in",
        "description": "Testing suffix starting with a dot"
    }
    response = await client.post(
        "/tenant/onboarding",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_onboarding_suffix_ending_with_dot_fails(client, admin_token):
    """Validate that tenant onboarding is rejected when the email suffix ends with a dot"""
    payload = {
        "name": "Kamla Nehru Institute of Technology",
        "email_suffix": "knit.edu.in.",
        "description": "Testing suffix ending with a dot"
    }
    response = await client.post(
        "/tenant/onboarding",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_onboarding_suffix_with_double_dots_fails(client, admin_token):
    """Validate that tenant onboarding is rejected when the email suffix contains consecutive dots"""
    payload = {
        "name": "Kamla Nehru Institute of Technology",
        "email_suffix": "knit..edu.in",
        "description": "Testing suffix with double dots"
    }
    response = await client.post(
        "/tenant/onboarding",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_onboarding_suffix_with_at_symbol_fails(client, admin_token):
    """Validate that tenant onboarding is rejected when the email suffix contains an at symbol"""
    payload = {
        "name": "Kamla Nehru Institute of Technology",
        "email_suffix": "admin@knit.edu.in",
        "description": "Testing suffix with an @ symbol"
    }
    response = await client.post(
        "/tenant/onboarding",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 422