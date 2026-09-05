import pytest

from app.core.token import create_access_token


@pytest.mark.asyncio
async def test_onboarding_success(client, admin_token):
    """Verify that tenant onboarding succeeds for an admin with a valid token"""
    payload = {
        "name": "Kamla Nehru Institute of Technology",
        "slug": "knit",
        "vertical": "campus_club",
        "description": "Kamla Nehru Institute of Technology",
    }
    response = await client.post(
        "/tenant/onboarding",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == "knit"
    assert body["vertical"] == "campus_club"
    assert body["message"] == "Tenant onboarded successfully"


@pytest.mark.asyncio
async def test_onboarding_without_token_fails(client):
    """Verify that tenant onboarding is rejected when no authentication token is provided"""
    payload = {
        "name": "Kamla Nehru Institute of Technology",
        "slug": "knit",
        "vertical": "campus_club",
        "description": "Kamla Nehru Institute of Technology",
    }
    response = await client.post("/tenant/onboarding", json=payload)
    assert response.status_code == 401
    body = response.json()
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
        "slug": "some-tenant",
        "vertical": "campus_club",
        "description": "Just to create a member for this test",
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
        "role": "MEMBER",
        "tenant_slug": "some-tenant",
    }
    member_signup = await client.post("/auth/signup", json=member_payload)
    member_token = member_signup.json()["access_token"]

    onboarding_payload = {
        "name": "Another Tenant Institute",
        "slug": "another-tenant",
        "vertical": "campus_club",
        "description": "A member should not be able to do this",
    }
    response = await client.post(
        "/tenant/onboarding",
        json=onboarding_payload,
        headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 403
    body = response.json()
    assert body["message"] == "You do not have permission for this"


@pytest.mark.asyncio
async def test_onboarding_duplicate_tenant_fails(client, admin_token):
    """Verify that tenant onboarding is rejected when the tenant already exists"""
    tenant_payload = {
        "name": "Kamla Nehru Institute of Technology",
        "slug": "knit",
        "vertical": "campus_club",
        "description": "Kamla Nehru Institute of Technology",
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
        "slug": "knit",
        "vertical": "campus_club",
        "description": "Kamla Nehru Institute of Technology",
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
        "slug": "shortname",
        "vertical": "campus_club",
        "description": "Name is too short here",
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
        "slug": "shortdesc",
        "vertical": "campus_club",
        "description": "Hi",
    }
    response = await client.post(
        "/tenant/onboarding",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_onboarding_slug_collision_fails(client, admin_token):
    """Verify that tenant onboarding rejects a second tenant reusing an already-taken slug."""
    first_payload = {
        "name": "Kamla Nehru Institute of Technology",
        "slug": "knit",
        "vertical": "campus_club",
        "description": "First tenant with this slug",
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
        "slug": "knit",
        "vertical": "campus_club",
        "description": "Second tenant colliding on the same slug",
    }
    response = await client.post(
        "/tenant/onboarding",
        json=second_payload,
        headers={"Authorization": f"Bearer {second_token}"}
    )
    assert response.status_code == 409
    assert response.json()["message"] == "Tenant already registered"

@pytest.mark.asyncio
async def test_onboarding_unknown_vertical_fails(client, admin_token):
    """Onboarding a tenant against a vertical with no manifest fails fast rather than
    creating a tenant with no configuration to fall back to."""
    payload = {
        "name": "Kamla Nehru Institute of Technology",
        "slug": "knit-unknown",
        "vertical": "not_a_real_vertical",
        "description": "Testing an unknown vertical",
    }
    response = await client.post(
        "/tenant/onboarding",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 422
    assert response.json()["message"] == "Unknown vertical"


# ==== GET /api/t/{slug}/tenant (tenant identity for the frontend shell) ====

@pytest.mark.asyncio
async def test_get_tenant_info_as_member_success(client, member_token, seed_tenant):
    """A MEMBER of the tenant can fetch its identity/config."""
    response = await client.get(
        f"/api/t/{seed_tenant.slug}/tenant",
        headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == seed_tenant.name
    assert body["slug"] == seed_tenant.slug
    assert body["vertical"] == seed_tenant.vertical
    assert body["description"] == seed_tenant.description
    assert body["enabled_packs"] == seed_tenant.enabled_packs
    assert body["timezone"] == seed_tenant.timezone


@pytest.mark.asyncio
async def test_get_tenant_info_as_tenant_admin_success(client, tenant_admin, seed_tenant):
    """A TENANT_ADMIN of the tenant can fetch its identity/config too."""
    response = await client.get(
        f"/api/t/{seed_tenant.slug}/tenant",
        headers=tenant_admin,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == seed_tenant.slug
    assert body["vertical"] == seed_tenant.vertical


@pytest.mark.asyncio
async def test_get_tenant_info_cross_tenant_slug_mismatch_fails(client, member_token):
    """A token issued for one tenant must not read another tenant's slug in the URL."""
    response = await client.get(
        "/api/t/some-other-tenant/tenant",
        headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 403
    assert response.json()["message"] == "Tenant mismatch"


@pytest.mark.asyncio
async def test_get_tenant_info_unknown_slug_not_found(client):
    """A token whose own tenant_slug claim matches the URL but whose tenant
    no longer exists in the database 404s rather than leaking anything."""
    ghost_token = create_access_token({
        "sub": "999999",
        "full_name": "Ghost Member",
        "email": "ghost@nowhere.test",
        "role": "MEMBER",
        "tenant_id": 999999,
        "tenant_slug": "ghost-tenant",
    })
    response = await client.get(
        "/api/t/ghost-tenant/tenant",
        headers={"Authorization": f"Bearer {ghost_token}"}
    )
    assert response.status_code == 404
    assert response.json()["message"] == "Tenant not registered"


@pytest.mark.asyncio
async def test_get_tenant_info_without_token_fails(client, seed_tenant):
    """Fetching tenant info is rejected when no authentication token is provided."""
    response = await client.get(f"/api/t/{seed_tenant.slug}/tenant")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_onboarding_invalid_slug_characters_fail(client, admin_token):
    """Validate that tenant onboarding is rejected when the slug does not match the slug pattern."""
    payload = {
        "name": "Kamla Nehru Institute of Technology",
        "slug": "Not A Valid Slug!",
        "vertical": "campus_club",
        "description": "Testing an invalid slug",
    }
    response = await client.post(
        "/tenant/onboarding",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_onboarding_slug_too_short_fails(client, admin_token):
    """Validate that tenant onboarding is rejected when the slug is below the minimum length"""
    payload = {
        "name": "Kamla Nehru Institute of Technology",
        "slug": "ab",
        "vertical": "campus_club",
        "description": "Testing slug under minimum length",
    }
    response = await client.post(
        "/tenant/onboarding",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_onboarding_name_over_max_length_fails(client, admin_token):
    """Validate that tenant onboarding is rejected when the tenant name exceeds the maximum length"""
    payload = {
        "name": "A" * 101,
        "slug": "toolongname",
        "vertical": "campus_club",
        "description": "Testing name over max length",
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
        "slug": "toolongdesc",
        "vertical": "campus_club",
        "description": "A" * 1001,
    }
    response = await client.post(
        "/tenant/onboarding",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_onboarding_slug_over_max_length_fails(client, admin_token):
    """Validate that tenant onboarding is rejected when the slug exceeds the maximum length"""
    payload = {
        "name": "Kamla Nehru Institute of Technology",
        "slug": "a" * 101,
        "vertical": "campus_club",
        "description": "Testing slug over max length",
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
        "slug": "blankname",
        "vertical": "campus_club",
        "description": "Testing whitespace-only name",
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
        "slug": "blankdesc",
        "vertical": "campus_club",
        "description": "     ",
    }
    response = await client.post(
        "/tenant/onboarding",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_onboarding_slug_whitespace_and_case_is_normalized(client, admin_token):
    """Verify that leading/trailing whitespace and uppercase in the slug are normalized during onboarding"""
    payload = {
        "name": "Kamla Nehru Institute of Technology",
        "slug": " KNIT ",
        "vertical": "campus_club",
        "description": "Testing whitespace and case normalization on slug",
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
    assert body["description"] == "Testing whitespace and case normalization on slug"
    assert isinstance(body["slug"], str)
    assert len(body["slug"]) > 0
    assert body["message"] == "Tenant onboarded successfully"


@pytest.mark.asyncio
async def test_onboarding_slug_starting_with_hyphen_fails(client, admin_token):
    """Validate that tenant onboarding is rejected when the slug starts with a hyphen"""
    payload = {
        "name": "Kamla Nehru Institute of Technology",
        "slug": "-knit",
        "vertical": "campus_club",
        "description": "Testing slug starting with a hyphen",
    }
    response = await client.post(
        "/tenant/onboarding",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_onboarding_slug_ending_with_hyphen_fails(client, admin_token):
    """Validate that tenant onboarding is rejected when the slug ends with a hyphen"""
    payload = {
        "name": "Kamla Nehru Institute of Technology",
        "slug": "knit-",
        "vertical": "campus_club",
        "description": "Testing slug ending with a hyphen",
    }
    response = await client.post(
        "/tenant/onboarding",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_onboarding_slug_with_underscore_fails(client, admin_token):
    """Validate that tenant onboarding is rejected when the slug contains an underscore"""
    payload = {
        "name": "Kamla Nehru Institute of Technology",
        "slug": "knit_edu",
        "vertical": "campus_club",
        "description": "Testing slug with an underscore",
    }
    response = await client.post(
        "/tenant/onboarding",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_onboarding_slug_with_at_symbol_fails(client, admin_token):
    """Validate that tenant onboarding is rejected when the slug contains an at symbol"""
    payload = {
        "name": "Kamla Nehru Institute of Technology",
        "slug": "knit@edu",
        "vertical": "campus_club",
        "description": "Testing slug with an @ symbol",
    }
    response = await client.post(
        "/tenant/onboarding",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 422
