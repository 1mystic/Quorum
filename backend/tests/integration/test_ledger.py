"""
Card C.10 (ledger domain). Requires a real Postgres TEST_DATABASE_URL, same
constraint as `test_tenancy.py`: these are integration tests, not unit tests.

Follows a Due through the exact path the interview evidence in
`RWA_Master_Context.md` describes: raised, paid, verified by a treasurer,
receipted, and the receipt collected (or not).
"""
import pytest

from tests.conftest import tenant_path


@pytest.fixture
async def rwa_tenant(db_session):
    from app.models import Tenant

    tenant = Tenant(name="Vaikunth Heights", slug="vaikunth-heights", vertical="rwa_society")
    db_session.add(tenant)
    await db_session.flush()
    await db_session.refresh(tenant)
    return tenant


async def _signup_member(client, tenant_slug: str, email: str) -> tuple[str, dict]:
    payload = {
        "email": email,
        "full_name": "Ledger Test Member",
        "password": "Member@123",
        "confirm_password": "Member@123",
        "role": "MEMBER",
        "tenant_slug": tenant_slug,
    }
    response = await client.post("/api/auth/signup", json=payload)
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    profile = await client.get(tenant_path(tenant_slug, "/members/me"), headers=headers)
    assert profile.status_code == 200, profile.text
    return headers, profile.json()["member_id"]


@pytest.mark.asyncio
async def test_raise_a_due_and_settle_it_with_a_verified_receipted_payment(client, rwa_tenant):
    slug = rwa_tenant.slug
    headers, member_id = await _signup_member(client, slug, "resident@vaikunth.example")

    due_payload = {
        "member_id": member_id,
        "category": "maintenance_dues",
        "amount_minor": 500000,
        "due_at": "2026-07-01T00:00:00Z",
    }
    due_response = await client.post(
        tenant_path(slug, "/ledger/dues"), headers=headers, json=due_payload,
    )
    assert due_response.status_code == 200, due_response.text
    assert due_response.json()["status"] == "OPEN"
    due_id = due_response.json()["id"]

    payment_payload = {
        "amount_minor": 500000,
        "category": "maintenance_dues",
        "instrument": "upi",
        "at": "2026-07-03T10:00:00Z",
        "due_id": due_id,
    }
    payment_response = await client.post(
        tenant_path(slug, "/ledger/payments"), headers=headers, json=payment_payload,
    )
    assert payment_response.status_code == 200, payment_response.text
    assert payment_response.json()["status"] == "pending"
    payment_id = payment_response.json()["id"]

    verify_response = await client.patch(
        tenant_path(slug, f"/ledger/payments/{payment_id}/verify"), headers=headers,
    )
    assert verify_response.status_code == 200, verify_response.text
    assert verify_response.json()["status"] == "settled"
    assert verify_response.json()["verified_at"] is not None

    receipt_response = await client.post(
        tenant_path(slug, f"/ledger/payments/{payment_id}/receipt"), headers=headers,
    )
    assert receipt_response.status_code == 200, receipt_response.text
    assert receipt_response.json()["issued_at"] is not None
    assert receipt_response.json()["collected_at"] is None, "the receipt-collection gap starts unclosed"

    collect_response = await client.patch(
        tenant_path(slug, f"/ledger/payments/{payment_id}/receipt/collect"), headers=headers,
    )
    assert collect_response.status_code == 200, collect_response.text
    assert collect_response.json()["collected_at"] is not None


@pytest.mark.asyncio
async def test_a_due_in_an_undeclared_category_is_rejected(client, rwa_tenant):
    slug = rwa_tenant.slug
    headers, member_id = await _signup_member(client, slug, "resident2@vaikunth.example")

    response = await client.post(
        tenant_path(slug, "/ledger/dues"), headers=headers,
        json={
            "member_id": member_id, "category": "bribery_fund", "amount_minor": 1000,
            "due_at": "2026-07-01T00:00:00Z",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_an_expense_and_a_contribution_can_be_recorded(client, rwa_tenant):
    slug = rwa_tenant.slug
    headers, _ = await _signup_member(client, slug, "treasurer@vaikunth.example")

    expense_response = await client.post(
        tenant_path(slug, "/ledger/expenses"), headers=headers,
        json={
            "category": "stp_maintenance", "amount_minor": 75000, "instrument": "bank_transfer",
            "at": "2026-07-05T00:00:00Z", "counterparty_ref": "vendor_a",
        },
    )
    assert expense_response.status_code == 200, expense_response.text
    assert expense_response.json()["amount_minor"] == 75000

    contribution_response = await client.post(
        tenant_path(slug, "/ledger/contributions"), headers=headers,
        json={
            "kind": "cash", "category": "festival_fund", "at": "2026-07-06T00:00:00Z",
            "amount_minor": 10000,
        },
    )
    assert contribution_response.status_code == 200, contribution_response.text
    assert contribution_response.json()["amount_minor"] == 10000
