"""
Cross-tenant isolation (docs/RULES.md section 5, card C.5).

Campus Connect scoped data by college but never had a hostile tenant. Quorum
does, so isolation is a test suite, not a comment: a cross-tenant read must
403 at the API *and* return zero rows under Postgres row-level security with
the API bypassed entirely.

Requires a real Postgres TEST_DATABASE_URL - these are integration tests, not
unit tests, and the RLS test in particular is only meaningful against a real
server (SQLite has no row-level security to prove).
"""
import pytest
from sqlalchemy import text

from app.models import Tenant


async def _signup_member(client, tenant_slug: str, email: str) -> str:
    payload = {
        "email": email,
        "full_name": "Isolation Test Member",
        "password": "Member@123",
        "confirm_password": "Member@123",
        "role": "MEMBER",
        "tenant_slug": tenant_slug,
    }
    response = await client.post("/api/auth/signup", json=payload)
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture
async def two_tenants(db_session):
    tenant_a = Tenant(name="Society A", slug="society-a", vertical="rwa_society")
    tenant_b = Tenant(name="Society B", slug="society-b", vertical="rwa_society")
    db_session.add_all([tenant_a, tenant_b])
    await db_session.flush()
    await db_session.refresh(tenant_a)
    await db_session.refresh(tenant_b)
    return tenant_a, tenant_b


@pytest.mark.asyncio
async def test_cross_tenant_read_is_forbidden_at_the_api(client, two_tenants):
    """
    A token issued for society-a must not read society-b's data, even though
    both slugs are valid tenants and the token itself is valid.
    """
    tenant_a, tenant_b = two_tenants
    token_a = await _signup_member(client, tenant_a.slug, "member-a@example.com")

    response = await client.get(
        f"/api/t/{tenant_b.slug}/requests",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_same_tenant_read_is_allowed(client, two_tenants):
    """The 403 above is a tenant check, not a blanket failure of the route."""
    tenant_a, _ = two_tenants
    token_a = await _signup_member(client, tenant_a.slug, "member-a2@example.com")

    response = await client.get(
        f"/api/t/{tenant_a.slug}/requests",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_forged_slug_without_matching_claim_is_forbidden(client, two_tenants):
    """
    Never trust the URL alone: a request for a tenant the caller has never
    even signed up under must 403, not 404 - the mismatch is caught before
    any lookup for tenant_b happens.
    """
    tenant_a, tenant_b = two_tenants
    token_a = await _signup_member(client, tenant_a.slug, "member-a3@example.com")

    response = await client.get(
        f"/api/t/{tenant_b.slug}/groups",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_no_token_on_tenant_route_is_rejected(client, two_tenants):
    tenant_a, _ = two_tenants
    response = await client.get(f"/api/t/{tenant_a.slug}/requests")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_rls_hides_cross_tenant_rows_with_the_api_bypassed(db_session, two_tenants):
    """
    Same guarantee as the API-level tests above, proven at the SQL layer with
    the application (and TenantScopedRepository) entirely out of the loop.
    This is what makes RLS a real backstop rather than a second copy of the
    same application-level check.

    Requires the test database role to NOT be a superuser/table owner bypass
    - RLS (even FORCE RLS) does not apply to a table's owner unless the
    connecting role is a plain grantee. If this test starts passing
    vacuously (rows visible under every tenant_id), check the role
    TEST_DATABASE_URL connects as.
    """
    tenant_a, tenant_b = two_tenants

    async def set_tenant(tenant_id: int):
        await db_session.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )

    # Seed one member + one group + one request per tenant, all under
    # tenant A's session context so the rows are attributed correctly.
    await set_tenant(tenant_a.id)
    await db_session.execute(text(
        "INSERT INTO users (tenant_id, email, full_name, role) "
        "VALUES (:tid, 'rls-a@example.com', 'RLS A', 'MEMBER')"
    ), {"tid": tenant_a.id})
    user_a_id = (await db_session.execute(
        text("SELECT id FROM users WHERE email = 'rls-a@example.com'")
    )).scalar_one()
    await db_session.execute(text(
        "INSERT INTO members (tenant_id, user_id) VALUES (:tid, :uid)"
    ), {"tid": tenant_a.id, "uid": user_a_id})
    member_a_id = (await db_session.execute(
        text("SELECT id FROM members WHERE user_id = :uid"), {"uid": user_a_id}
    )).scalar_one()
    await db_session.execute(text(
        "INSERT INTO groups (tenant_id, group_head, name, description, category, type, status) "
        "VALUES (:tid, :head, 'Maintenance Committee', 'desc', 'GENERAL', 'OFFICIAL', 'ACTIVE')"
    ), {"tid": tenant_a.id, "head": member_a_id})
    group_a_id = (await db_session.execute(
        text("SELECT id FROM groups WHERE tenant_id = :tid"), {"tid": tenant_a.id}
    )).scalar_one()
    await db_session.execute(text(
        "INSERT INTO requests (tenant_id, member_id, group_id, category, status, title, description) "
        "VALUES (:tid, :mid, :gid, 'GENERAL', 'OPEN', 'Leaking pipe', 'A tenant-A-only request')"
    ), {"tid": tenant_a.id, "mid": member_a_id, "gid": group_a_id})
    await db_session.flush()

    # Now read as tenant B: RLS should hide every row seeded above.
    await set_tenant(tenant_b.id)
    visible_requests = (await db_session.execute(text("SELECT id FROM requests"))).scalars().all()
    visible_groups = (await db_session.execute(text("SELECT id FROM groups"))).scalars().all()
    visible_members = (await db_session.execute(text("SELECT id FROM members"))).scalars().all()

    assert visible_requests == []
    assert visible_groups == []
    assert visible_members == []

    # Sanity check: the rows really exist and are visible under their own tenant.
    await set_tenant(tenant_a.id)
    own_requests = (await db_session.execute(text("SELECT id FROM requests"))).scalars().all()
    assert len(own_requests) == 1
