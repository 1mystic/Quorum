import pytest


# ==== fixtures ====

@pytest.fixture
async def leader(client, seed_tenant):
    """A member who owns an active group. Yields (headers, group_id)."""
    payload = {
        "email": "leader@knit.edu.in",
        "full_name": "Group Leader",
        "password": "Test@1234",
        "confirm_password": "Test@1234",
        "role": "MEMBER",
        "tenant_slug": seed_tenant.slug,
    }
    signup = await client.post("/auth/signup", json=payload)
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    payload = {
        "name": "Robotics Group",
        "description": "A group for building robots and breaking budgets",
        "category": "Technical",
        "type": "UNOFFICIAL",
    }
    group = await client.post("/groups", headers=headers, json=payload)
    return headers, group.json()["id"]


@pytest.fixture
async def member(client, seed_tenant, leader):
    """An approved member of the leader's group."""
    leader_headers, group_id = leader
    payload = {
        "email": "member@knit.edu.in",
        "full_name": "Group Member",
        "password": "Test@1234",
        "confirm_password": "Test@1234",
        "role": "MEMBER",
        "tenant_slug": seed_tenant.slug,
    }
    signup = await client.post("/auth/signup", json=payload)
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    join = await client.post(f"/groups/{group_id}/join", headers=headers)
    await client.patch(
        f"/groups/{group_id}/requests/{join.json()['id']}",
        headers=leader_headers,
        json={"action": "APPROVED"},
    )
    return headers


@pytest.fixture
async def outsider(client, seed_tenant):
    """A member of the same tenant who belongs to no group."""
    payload = {
        "email": "outsider@knit.edu.in",
        "full_name": "Outsider Member",
        "password": "Test@1234",
        "confirm_password": "Test@1234",
        "role": "MEMBER",
        "tenant_slug": seed_tenant.slug,
    }
    signup = await client.post("/auth/signup", json=payload)
    return {"Authorization": f"Bearer {signup.json()['access_token']}"}


def _decision_payload(group_id):
    return {
        "group_id": group_id,
        "title": "Which lab kit should we buy?",
        "description": "A poll to decide the next robotics kit purchase",
        "kind": "poll",
        "declared_rule": "approval",
        "ballot_style": "approval",
        "options": [
            {"label": "Kit A"},
            {"label": "Kit B"},
        ],
    }


# ==== create decision ====

@pytest.mark.asyncio
async def test_create_decision_by_leader_success(client, leader):
    """Verify that a group leader can create a decision for their own group, as a draft"""
    headers, group_id = leader
    response = await client.post("/decisions", headers=headers, json=_decision_payload(group_id))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "DRAFT"
    assert body["opened_at"] is None
    assert len(body["options"]) == 2


@pytest.mark.asyncio
async def test_create_decision_by_admin_for_group_success(client, leader, tenant_admin):
    """Verify that a tenant admin can create a decision for any group"""
    _, group_id = leader
    response = await client.post("/decisions", headers=tenant_admin, json=_decision_payload(group_id))
    assert response.status_code == 200
    assert response.json()["status"] == "DRAFT"


@pytest.mark.asyncio
async def test_create_decision_by_non_leader_fails(client, leader, member):
    """Ensure that a plain group member cannot create a decision for the group"""
    _, group_id = leader
    response = await client.post("/decisions", headers=member, json=_decision_payload(group_id))
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_decision_by_outsider_fails(client, leader, outsider):
    """Ensure that a member outside the group cannot create a decision for it"""
    _, group_id = leader
    response = await client.post("/decisions", headers=outsider, json=_decision_payload(group_id))
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_tenant_wide_decision_by_member_fails(client, leader):
    """Ensure a tenant-wide decision (no group_id) needs a TenantAdmin, not any leader"""
    headers, _ = leader
    payload = _decision_payload(None)
    payload["group_id"] = None
    response = await client.post("/decisions", headers=headers, json=payload)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_tenant_wide_decision_by_admin_success(client, tenant_admin):
    """Verify that a TenantAdmin can create a tenant-wide decision"""
    payload = _decision_payload(None)
    payload["group_id"] = None
    response = await client.post("/decisions", headers=tenant_admin, json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "DRAFT"


@pytest.mark.asyncio
async def test_create_decision_invalid_declared_rule_fails(client, leader):
    """Confirm that an undeclared voting rule is rejected"""
    headers, group_id = leader
    payload = _decision_payload(group_id)
    payload["declared_rule"] = "majority_vibes"
    response = await client.post("/decisions", headers=headers, json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_decision_without_token_fails(client, leader):
    """Ensure decision creation is rejected without an access token"""
    _, group_id = leader
    response = await client.post("/decisions", json=_decision_payload(group_id))
    assert response.status_code == 401


# ==== submit for review ====

@pytest.mark.asyncio
async def test_submit_decision_for_review_success(client, leader):
    """Verify that the leader who can manage the decision can submit it for review"""
    headers, group_id = leader
    create = await client.post("/decisions", headers=headers, json=_decision_payload(group_id))
    decision_id = create.json()["id"]

    response = await client.patch(f"/decisions/{decision_id}/submit-for-review", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "SUBMITTED"


@pytest.mark.asyncio
async def test_submit_decision_for_review_by_non_leader_fails(client, leader, member):
    """Ensure a plain member cannot submit the group's decision for review"""
    headers, group_id = leader
    create = await client.post("/decisions", headers=headers, json=_decision_payload(group_id))
    decision_id = create.json()["id"]

    response = await client.patch(f"/decisions/{decision_id}/submit-for-review", headers=member)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_submit_already_submitted_decision_fails(client, leader):
    """Confirm that a decision already submitted cannot be submitted again"""
    headers, group_id = leader
    create = await client.post("/decisions", headers=headers, json=_decision_payload(group_id))
    decision_id = create.json()["id"]
    await client.patch(f"/decisions/{decision_id}/submit-for-review", headers=headers)

    response = await client.patch(f"/decisions/{decision_id}/submit-for-review", headers=headers)
    assert response.status_code == 403


# ==== approve ====

@pytest.mark.asyncio
async def test_approve_decision_success_opens_voting(client, leader, tenant_admin):
    """Verify that approving a submitted decision opens it for voting and freezes the roster"""
    headers, group_id = leader
    create = await client.post("/decisions", headers=headers, json=_decision_payload(group_id))
    decision_id = create.json()["id"]
    await client.patch(f"/decisions/{decision_id}/submit-for-review", headers=headers)

    response = await client.patch(f"/decisions/{decision_id}/approve", headers=tenant_admin)
    assert response.status_code == 200
    assert response.json()["status"] == "OPEN"

    detail = await client.get(f"/decisions/{decision_id}", headers=headers)
    body = detail.json()
    assert body["status"] == "OPEN"
    assert body["opened_at"] is not None


@pytest.mark.asyncio
async def test_approve_draft_decision_fails(client, leader, tenant_admin):
    """Confirm that a draft decision cannot be approved before it is submitted"""
    headers, group_id = leader
    create = await client.post("/decisions", headers=headers, json=_decision_payload(group_id))
    decision_id = create.json()["id"]

    response = await client.patch(f"/decisions/{decision_id}/approve", headers=tenant_admin)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_approve_decision_by_non_admin_fails(client, leader):
    """Ensure that a group leader cannot approve their own submission"""
    headers, group_id = leader
    create = await client.post("/decisions", headers=headers, json=_decision_payload(group_id))
    decision_id = create.json()["id"]
    await client.patch(f"/decisions/{decision_id}/submit-for-review", headers=headers)

    response = await client.patch(f"/decisions/{decision_id}/approve", headers=headers)
    assert response.status_code == 403


# ==== reject ====

@pytest.mark.asyncio
async def test_reject_decision_success_and_resubmit(client, leader, tenant_admin):
    """A rejection carries a reason and returns the decision to a resubmittable state"""
    headers, group_id = leader
    create = await client.post("/decisions", headers=headers, json=_decision_payload(group_id))
    decision_id = create.json()["id"]
    await client.patch(f"/decisions/{decision_id}/submit-for-review", headers=headers)

    response = await client.patch(
        f"/decisions/{decision_id}/reject", headers=tenant_admin,
        json={"reason": "Needs a third option before it can open"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "REJECTED"
    assert response.json()["rejection_reason"] == "Needs a third option before it can open"

    resubmit = await client.patch(f"/decisions/{decision_id}/submit-for-review", headers=headers)
    assert resubmit.status_code == 200
    assert resubmit.json()["status"] == "SUBMITTED"

    approve = await client.patch(f"/decisions/{decision_id}/approve", headers=tenant_admin)
    assert approve.status_code == 200
    assert approve.json()["status"] == "OPEN"


@pytest.mark.asyncio
async def test_reject_decision_not_submitted_fails(client, leader, tenant_admin):
    """Confirm that a draft decision cannot be rejected before it is submitted"""
    headers, group_id = leader
    create = await client.post("/decisions", headers=headers, json=_decision_payload(group_id))
    decision_id = create.json()["id"]

    response = await client.patch(
        f"/decisions/{decision_id}/reject", headers=tenant_admin, json={"reason": "Too early"}
    )
    assert response.status_code == 403


# ==== cast ballot ====

@pytest.mark.asyncio
async def test_cast_ballot_before_open_fails(client, leader, member):
    """Confirm that a draft decision (never opened) refuses ballots"""
    headers, group_id = leader
    create = await client.post("/decisions", headers=headers, json=_decision_payload(group_id))
    body = create.json()
    decision_id = body["id"]
    option_id = body["options"][0]["id"]

    response = await client.post(
        f"/decisions/{decision_id}/ballots", headers=member, json={"approvals": [option_id]}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_cast_ballot_while_submitted_fails(client, leader, member):
    """Confirm that a submitted-but-not-approved decision still refuses ballots"""
    headers, group_id = leader
    create = await client.post("/decisions", headers=headers, json=_decision_payload(group_id))
    body = create.json()
    decision_id = body["id"]
    option_id = body["options"][0]["id"]
    await client.patch(f"/decisions/{decision_id}/submit-for-review", headers=headers)

    response = await client.post(
        f"/decisions/{decision_id}/ballots", headers=member, json={"approvals": [option_id]}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_cast_ballot_after_open_success(client, leader, member, tenant_admin):
    """Verify that a member can cast a ballot once a decision is open for voting"""
    headers, group_id = leader
    create = await client.post("/decisions", headers=headers, json=_decision_payload(group_id))
    body = create.json()
    decision_id = body["id"]
    option_id = body["options"][0]["id"]
    await client.patch(f"/decisions/{decision_id}/submit-for-review", headers=headers)
    await client.patch(f"/decisions/{decision_id}/approve", headers=tenant_admin)

    response = await client.post(
        f"/decisions/{decision_id}/ballots", headers=member, json={"approvals": [option_id]}
    )
    assert response.status_code == 200
    assert response.json()["approvals"] == [option_id]


@pytest.mark.asyncio
async def test_cast_ballot_after_close_fails(client, leader, member, tenant_admin):
    """Confirm that a closed decision refuses further ballots"""
    headers, group_id = leader
    create = await client.post("/decisions", headers=headers, json=_decision_payload(group_id))
    body = create.json()
    decision_id = body["id"]
    option_id = body["options"][0]["id"]
    await client.patch(f"/decisions/{decision_id}/submit-for-review", headers=headers)
    await client.patch(f"/decisions/{decision_id}/approve", headers=tenant_admin)
    await client.patch(f"/decisions/{decision_id}/close", headers=headers)

    response = await client.post(
        f"/decisions/{decision_id}/ballots", headers=member, json={"approvals": [option_id]}
    )
    assert response.status_code == 409


# ==== list decisions ====

@pytest.mark.asyncio
async def test_list_decisions_serializes_options(client, leader):
    """
    Regression: GET /decisions used to raise sqlalchemy.exc.MissingGreenlet
    because DecisionRepository.list_decisions never eager-loaded `options`,
    unlike get_by_id - DecisionItem._item reads decision.options, which
    lazy-loaded outside the async session context during response
    serialization. Only reproduces against a real async driver (asyncpg),
    which is why this must run against Postgres, not a sync-shimmed DB.
    """
    headers, group_id = leader
    create = await client.post("/decisions", headers=headers, json=_decision_payload(group_id))
    assert create.status_code == 200

    response = await client.get("/decisions", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) >= 1
    assert any(len(d["options"]) == 2 for d in body)


# ==== close decision ====

@pytest.mark.asyncio
async def test_close_decision_requires_open(client, leader):
    """Confirm that a draft decision (never opened) cannot be closed"""
    headers, group_id = leader
    create = await client.post("/decisions", headers=headers, json=_decision_payload(group_id))
    decision_id = create.json()["id"]

    response = await client.patch(f"/decisions/{decision_id}/close", headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_close_open_decision_success(client, leader, tenant_admin):
    """Verify that an open decision can be closed by its leader"""
    headers, group_id = leader
    create = await client.post("/decisions", headers=headers, json=_decision_payload(group_id))
    decision_id = create.json()["id"]
    await client.patch(f"/decisions/{decision_id}/submit-for-review", headers=headers)
    await client.patch(f"/decisions/{decision_id}/approve", headers=tenant_admin)

    response = await client.patch(f"/decisions/{decision_id}/close", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "CLOSED"


@pytest.mark.asyncio
async def test_close_decision_twice_fails(client, leader, tenant_admin):
    """Confirm that closing an already-closed decision is rejected"""
    headers, group_id = leader
    create = await client.post("/decisions", headers=headers, json=_decision_payload(group_id))
    decision_id = create.json()["id"]
    await client.patch(f"/decisions/{decision_id}/submit-for-review", headers=headers)
    await client.patch(f"/decisions/{decision_id}/approve", headers=tenant_admin)
    await client.patch(f"/decisions/{decision_id}/close", headers=headers)

    response = await client.patch(f"/decisions/{decision_id}/close", headers=headers)
    assert response.status_code == 409
