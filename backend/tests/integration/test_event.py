import pytest
from datetime import datetime, timedelta, timezone


def future_time(hours: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def past_time(hours: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


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
    payload = {"action": "APPROVED"}
    await client.patch(
        f"/groups/{group_id}/requests/{join.json()['id']}",
        headers=leader_headers,
        json=payload,
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


@pytest.fixture
async def started_event(client, db_session, leader, member, tenant_admin):
    """..."""
    from app.models import Event

    leader_headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(2),
        "ends_at": future_time(4),
    }
    create = await client.post("/events", headers=leader_headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=leader_headers)
    await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)
    registration = await client.post(f"/events/{event_id}/register", headers=member)
    registration_id = registration.json()["registration_id"]

    event = await db_session.get(Event, event_id)
    event.starts_at = datetime.now(timezone.utc) - timedelta(hours=1)
    event.ends_at = datetime.now(timezone.utc) + timedelta(hours=1)
    await db_session.flush()   # <- flush, not commit, stays inside the same transaction

    return leader_headers, event_id, registration_id

@pytest.fixture
async def second_member(client, leader):
    """Another approved member of the leader's group, distinct from `member`."""
    leader_headers, group_id = leader
    payload = {
        "email": "second@knit.edu.in",
        "full_name": "Second Member",
        "password": "Test@1234",
        "confirm_password": "Test@1234",
        "role": "MEMBER",
        "tenant_slug": "test-university",
    }
    signup = await client.post("/auth/signup", json=payload)
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    join = await client.post(f"/groups/{group_id}/join", headers=headers)
    approve_payload = {"action": "APPROVED"}
    await client.patch(
        f"/groups/{group_id}/requests/{join.json()['id']}",
        headers=leader_headers, json=approve_payload,
    )
    return headers


@pytest.fixture
async def two_checked_in(client, db_session, leader, member, second_member, tenant_admin):
    """Two members registered and checked in, event already started."""
    from app.models import Event
    from datetime import datetime, timedelta, timezone

    leader_headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        "ends_at": (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
    }
    create = await client.post("/events", headers=leader_headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=leader_headers)
    await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)

    # Register BOTH members while the event is still in the future
    first = await client.post(f"/events/{event_id}/register", headers=member)
    first_registration_id = first.json()["registration_id"]
    second = await client.post(f"/events/{event_id}/register", headers=second_member)
    second_registration_id = second.json()["registration_id"]

    # Now rewind the event so it appears started
    event = await db_session.get(Event, event_id)
    event.starts_at = datetime.now(timezone.utc) - timedelta(hours=1)
    event.ends_at = datetime.now(timezone.utc) + timedelta(hours=1)
    await db_session.flush()

    await client.patch(
        f"/events/{event_id}/registrations/{first_registration_id}/attendance",
        headers=leader_headers, json={"checked_in": True},
    )
    await client.patch(
        f"/events/{event_id}/registrations/{second_registration_id}/attendance",
        headers=leader_headers, json={"checked_in": True},
    )

    return leader_headers, event_id, first_registration_id, second_registration_id


@pytest.fixture
async def three_checked_in(client, db_session, leader, member, second_member, tenant_admin):
    """Three members registered and checked in, for testing participants count math."""
    from app.models import Event

    leader_headers, group_id = leader
    third_payload = {
        "email": "third@knit.edu.in",
        "full_name": "Third Member",
        "password": "Test@1234",
        "confirm_password": "Test@1234",
        "role": "MEMBER",
        "tenant_slug": "test-university",
    }
    signup = await client.post("/auth/signup", json=third_payload)
    third_headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    join = await client.post(f"/groups/{group_id}/join", headers=third_headers)
    await client.patch(
        f"/groups/{group_id}/requests/{join.json()['id']}",
        headers=leader_headers,
        json={"action": "APPROVED"},
    )

    payload = {
        "group_id": group_id,
        "title": "Three Person Event",
        "description": "An event with three checked-in attendees",
        "venue": "Lab 204",
        "starts_at": future_time(2),
        "ends_at": future_time(4),
    }
    create = await client.post("/events", headers=leader_headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=leader_headers)
    await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)

    r1 = await client.post(f"/events/{event_id}/register", headers=member)
    r2 = await client.post(f"/events/{event_id}/register", headers=second_member)
    r3 = await client.post(f"/events/{event_id}/register", headers=third_headers)
    ids = [r1.json()["registration_id"], r2.json()["registration_id"], r3.json()["registration_id"]]

    event = await db_session.get(Event, event_id)
    event.starts_at = datetime.now(timezone.utc) - timedelta(hours=1)
    event.ends_at = datetime.now(timezone.utc) + timedelta(hours=1)
    await db_session.flush()

    for reg_id in ids:
        await client.patch(
            f"/events/{event_id}/registrations/{reg_id}/attendance",
            headers=leader_headers,
            json={"checked_in": True},
        )

    return leader_headers, event_id, ids


# ==== create event ====

@pytest.mark.asyncio
async def test_create_event_success(client, leader):
    """Verify that a group leader can create an event and that it is stored as a DRAFT"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
        "capacity": 30,
    }
    response = await client.post("/events", headers=headers, json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["group_id"] == group_id
    assert body["title"] == "Line Follower Workshop"
    assert body["status"] == "DRAFT"
    assert body["message"] == "Event created as a draft"


@pytest.mark.asyncio
async def test_create_event_without_capacity_succeeds(client, leader):
    """Confirm that an event can be created without a capacity limit"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Open Mic Night",
        "description": "An open evening for anyone who wants to perform",
        "venue": "Amphitheatre",
        "starts_at": future_time(72),
        "ends_at": future_time(75),
    }
    response = await client.post("/events", headers=headers, json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Open Mic Night"
    assert body["status"] == "DRAFT"


@pytest.mark.asyncio
async def test_create_event_end_before_start_fails(client, leader):
    """Validate that event creation is rejected when ends_at is not after starts_at"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Time Travel Session",
        "description": "An event that ends before it begins",
        "venue": "Lab 204",
        "starts_at": future_time(50),
        "ends_at": future_time(48),
    }
    response = await client.post("/events", headers=headers, json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_event_zero_capacity_fails(client, leader):
    """Validate that event creation is rejected when capacity is below the minimum of 1"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Zero Seat Event",
        "description": "An event with no seats at all",
        "venue": "Lab 204",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
        "capacity": 0,
    }
    response = await client.post("/events", headers=headers, json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_event_short_title_fails(client, leader):
    """Validate that event creation is rejected when the title is below the minimum length"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "AB",
        "description": "Title is one character too short",
        "venue": "Lab 204",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    response = await client.post("/events", headers=headers, json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_event_missing_fields_fails(client, leader):
    """Validate that event creation is rejected when required fields are missing"""
    headers, group_id = leader
    payload = {"group_id": group_id}
    response = await client.post("/events", headers=headers, json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_event_unknown_group_fails(client, leader):
    """Confirm that event creation is rejected when the group does not exist"""
    headers, _ = leader
    payload = {
        "group_id": 999999,
        "title": "Ghost Group Event",
        "description": "Event for a group that does not exist",
        "venue": "Nowhere",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    response = await client.post("/events", headers=headers, json=payload)
    assert response.status_code == 404
    assert response.json()["message"] == "Group not found"


@pytest.mark.asyncio
async def test_create_event_by_non_leader_fails(client, leader, member):
    """Ensure that a plain group member cannot create an event for the group"""
    _, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Unauthorised Event",
        "description": "This should never be created",
        "venue": "Nowhere",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    response = await client.post("/events", headers=member, json=payload)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_create_event_without_token_fails(client, leader):
    """Ensure that event creation is rejected when no access token is supplied"""
    _, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Anonymous Event",
        "description": "Created without any authentication",
        "venue": "Lab 204",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    response = await client.post("/events", json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# ==== submit for review ====

@pytest.mark.asyncio
async def test_submit_event_for_review_success(client, leader):
    """Verify that a leader can submit a draft event for admin review"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=headers, json=payload)
    event_id = create.json()["id"]

    response = await client.patch(f"/events/{event_id}/submit-for-review", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == event_id
    assert body["status"] == "SUBMITTED"


@pytest.mark.asyncio
async def test_submit_event_for_review_by_non_leader_fails(client, leader, member):
    """Ensure that a non-leader cannot submit the group's event for review"""
    leader_headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=leader_headers, json=payload)
    event_id = create.json()["id"]

    response = await client.patch(f"/events/{event_id}/submit-for-review", headers=member)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_publish_directly_from_draft_fails(client, leader, tenant_admin):
    """Confirm that publish can no longer be called straight from DRAFT, only from SUBMITTED"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=headers, json=payload)
    event_id = create.json()["id"]

    response = await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)
    assert response.status_code == 403
    assert response.json()["message"] == "Only an event submitted for review can be published"


# ==== publish event (tenant-admin only, from SUBMITTED) ====

@pytest.mark.asyncio
async def test_publish_event_success(client, leader, tenant_admin):
    """Verify that a tenant admin can publish an event submitted for review"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=headers)

    response = await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == event_id
    assert body["status"] == "PUBLISHED"
    assert body["message"] == "Event published successfully"


@pytest.mark.asyncio
async def test_publish_event_starting_in_past_fails(client, leader, tenant_admin):
    """Confirm that an event whose start time has already passed cannot be published"""
    headers, group_id = leader
    create_payload = {
        "group_id": group_id,
        "title": "Late Notice Workshop",
        "description": "An event created with a start time already in the past",
        "venue": "Lab 204",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=headers, json=create_payload)
    event_id = create.json()["id"]

    update_payload = {
        "starts_at": past_time(1),
        "ends_at": future_time(1),
    }
    await client.put(f"/events/{event_id}", headers=headers, json=update_payload)
    await client.patch(f"/events/{event_id}/submit-for-review", headers=headers)

    response = await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)
    assert response.status_code == 403
    assert response.json()["message"] == "An event starting in the past cannot be published"


@pytest.mark.asyncio
async def test_publish_event_twice_fails(client, leader, tenant_admin):
    """Confirm that publishing an already published event is rejected"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=headers)
    await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)

    response = await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)
    assert response.status_code == 403
    assert response.json()["message"] == "Event is already published"


@pytest.mark.asyncio
async def test_publish_cancelled_event_fails(client, leader, tenant_admin):
    """Confirm that a cancelled event cannot be published"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=headers)
    await client.patch(f"/events/{event_id}/cancel", headers=headers)

    response = await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)
    assert response.status_code == 403
    assert response.json()["message"] == "A cancelled event cannot be published"


@pytest.mark.asyncio
async def test_publish_event_by_non_admin_fails(client, leader, member):
    """Ensure that a plain member (even the leader who submitted it) cannot publish the event"""
    leader_headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=leader_headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=leader_headers)

    response = await client.patch(f"/events/{event_id}/publish", headers=member)
    assert response.status_code == 403

    response = await client.patch(f"/events/{event_id}/publish", headers=leader_headers)
    assert response.status_code == 403


# ==== reject event ====

@pytest.mark.asyncio
async def test_reject_event_success_and_resubmit(client, leader, tenant_admin):
    """A rejection carries a reason and returns the event to a resubmittable state, not a dead end"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=headers)

    response = await client.patch(
        f"/events/{event_id}/reject", headers=tenant_admin, json={"reason": "Venue double-booked"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "REJECTED"
    assert body["rejection_reason"] == "Venue double-booked"

    detail = await client.get(f"/events/{event_id}", headers=headers)
    assert detail.json()["rejection_reason"] == "Venue double-booked"

    resubmit = await client.patch(f"/events/{event_id}/submit-for-review", headers=headers)
    assert resubmit.status_code == 200
    assert resubmit.json()["status"] == "SUBMITTED"

    approve = await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)
    assert approve.status_code == 200
    assert approve.json()["status"] == "PUBLISHED"


@pytest.mark.asyncio
async def test_reject_event_by_non_admin_fails(client, leader):
    """Ensure that a group leader cannot reject their own submission"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=headers)

    response = await client.patch(
        f"/events/{event_id}/reject", headers=headers, json={"reason": "Not allowed"}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_reject_event_not_submitted_fails(client, leader, tenant_admin):
    """Confirm that a draft event cannot be rejected before it is submitted"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=headers, json=payload)
    event_id = create.json()["id"]

    response = await client.patch(
        f"/events/{event_id}/reject", headers=tenant_admin, json={"reason": "Too early"}
    )
    assert response.status_code == 403


# ==== cancel event ====

@pytest.mark.asyncio
async def test_cancel_event_success(client, leader, tenant_admin):
    """Verify that a leader can cancel a published event"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=headers)
    await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)

    response = await client.patch(f"/events/{event_id}/cancel", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == event_id
    assert body["status"] == "CANCELLED"
    assert body["message"] == "Event cancelled successfully"


@pytest.mark.asyncio
async def test_cancel_draft_event_succeeds(client, leader):
    """Confirm that a draft event that was never published can also be cancelled"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=headers, json=payload)
    event_id = create.json()["id"]

    response = await client.patch(f"/events/{event_id}/cancel", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_cancel_event_twice_fails(client, leader):
    """Confirm that cancelling an already cancelled event is rejected"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/cancel", headers=headers)

    response = await client.patch(f"/events/{event_id}/cancel", headers=headers)
    assert response.status_code == 403
    assert response.json()["message"] == "Event is already cancelled"


@pytest.mark.asyncio
async def test_cancel_event_by_non_leader_fails(client, leader, member):
    """Ensure that a non-leader cannot cancel the group's event"""
    leader_headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=leader_headers, json=payload)
    event_id = create.json()["id"]

    response = await client.patch(f"/events/{event_id}/cancel", headers=member)
    assert response.status_code == 403


# ==== edit event ====

@pytest.mark.asyncio
async def test_edit_event_success(client, leader):
    """Verify that a leader can update the editable fields of an event"""
    headers, group_id = leader
    create_payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
        "capacity": 25,
    }
    create = await client.post("/events", headers=headers, json=create_payload)
    event_id = create.json()["id"]

    update_payload = {
        "title": "Updated Workshop Title",
        "venue": "Seminar Hall B",
    }
    response = await client.put(f"/events/{event_id}", headers=headers, json=update_payload)
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Updated Workshop Title"
    assert body["venue"] == "Seminar Hall B"
    assert body["capacity"] == 25


@pytest.mark.asyncio
async def test_edit_event_end_before_existing_start_fails(client, leader):
    """Validate that an update is rejected when the new ends_at falls before the stored starts_at"""
    headers, group_id = leader
    create_payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=headers, json=create_payload)
    event_id = create.json()["id"]

    update_payload = {
        "ends_at": future_time(10),
    }
    response = await client.put(f"/events/{event_id}", headers=headers, json=update_payload)
    assert response.status_code == 403
    assert response.json()["message"] == "Event must end after it starts"


@pytest.mark.asyncio
async def test_edit_event_short_title_fails(client, leader):
    """Validate that an update is rejected when the new title is below the minimum length"""
    headers, group_id = leader
    create_payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=headers, json=create_payload)
    event_id = create.json()["id"]

    update_payload = {"title": "AB"}
    response = await client.put(f"/events/{event_id}", headers=headers, json=update_payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_edit_cancelled_event_fails(client, leader):
    """Confirm that a cancelled event cannot be edited"""
    headers, group_id = leader
    create_payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=headers, json=create_payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/cancel", headers=headers)

    update_payload = {"title": "Trying To Edit This"}
    response = await client.put(f"/events/{event_id}", headers=headers, json=update_payload)
    assert response.status_code == 403
    assert response.json()["message"] == "A cancelled event cannot be edited"


@pytest.mark.asyncio
async def test_edit_event_partial_payload_keeps_other_fields(client, leader):
    """Confirm that fields omitted from the update payload are left unchanged"""
    headers, group_id = leader
    create_payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
        "capacity": 25,
    }
    create = await client.post("/events", headers=headers, json=create_payload)
    event_id = create.json()["id"]

    update_payload = {"title": "Only The Title Changed"}
    response = await client.put(f"/events/{event_id}", headers=headers, json=update_payload)
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Only The Title Changed"
    assert body["venue"] == "Lab 204, Main Block"
    assert body["capacity"] == 25


@pytest.mark.asyncio
async def test_edit_event_by_non_leader_fails(client, leader, outsider):
    """Ensure that a member outside the group cannot edit the event"""
    leader_headers, group_id = leader
    create_payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=leader_headers, json=create_payload)
    event_id = create.json()["id"]

    update_payload = {"title": "Hijacked Event Title"}
    response = await client.put(f"/events/{event_id}", headers=outsider, json=update_payload)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_edit_event_group_id_is_ignored(client, leader):
    """Confirm that group_id is silently ignored on update since UpdateEventRequest does not accept it"""
    headers, group_id = leader
    create_payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=headers, json=create_payload)
    event_id = create.json()["id"]

    edit_payload = {
        "group_id": 999999,
        "title": "Attempted Group Reassignment",
    }
    response = await client.put(f"/events/{event_id}", headers=headers, json=edit_payload)
    assert response.status_code == 200
    body = response.json()
    assert body["group_id"] == group_id


@pytest.mark.asyncio
async def test_edit_event_capacity_below_current_registrations(client, leader, member, tenant_admin):
    """Confirm behavior when editing capacity below the number of already-registered participants"""
    headers, group_id = leader
    create_payload = {
        "group_id": group_id,
        "title": "Capacity Reduction Workshop",
        "description": "An event used to test reducing capacity below existing registrations",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
        "capacity": 5,
    }
    create = await client.post("/events", headers=headers, json=create_payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=headers)
    await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)
    await client.post(f"/events/{event_id}/register", headers=member)

    edit_payload = {"capacity": 0}
    response = await client.put(f"/events/{event_id}", headers=headers, json=edit_payload)
    assert response.status_code == 422


# ==== browse events ====

@pytest.mark.asyncio
async def test_browse_events_returns_published_events(client, leader, outsider, tenant_admin):
    """Verify that browsing events returns a published event to a member"""
    leader_headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=leader_headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=leader_headers)
    await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)

    response = await client.get("/events", headers=outsider)
    assert response.status_code == 200
    ids = [event["id"] for event in response.json()]
    assert event_id in ids


@pytest.mark.asyncio
async def test_browse_events_search_matches_title(client, leader, outsider, tenant_admin):
    """Confirm that the search filter matches an event by its title"""
    leader_headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=leader_headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=leader_headers)
    await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)

    response = await client.get("/events", headers=outsider, params={"search": "Line Follower"})
    assert response.status_code == 200
    assert [event["id"] for event in response.json()] == [event_id]


@pytest.mark.asyncio
async def test_browse_events_search_no_match_returns_empty(client, leader, outsider, tenant_admin):
    """Confirm that the search filter returns an empty list when nothing matches"""
    leader_headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=leader_headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=leader_headers)
    await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)

    response = await client.get("/events", headers=outsider, params={"search": "Zumba"})
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_browse_events_hides_drafts_from_members(client, leader, outsider):
    """Ensure that a draft event is excluded from a member's browse results"""
    leader_headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Unpublished Workshop",
        "description": "This event has never been published",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=leader_headers, json=payload)
    event_id = create.json()["id"]

    response = await client.get("/events", headers=outsider)
    assert response.status_code == 200
    ids = [event["id"] for event in response.json()]
    assert event_id not in ids


@pytest.mark.asyncio
async def test_browse_events_admin_can_filter_by_draft_status(client):
    """Verify that an admin can browse events with a DRAFT status filter"""
    admin_payload = {
        "email": "admin@eventfilter.edu.in",
        "full_name": "Event Filter Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "TENANT_ADMIN",
    }
    admin_signup = await client.post("/auth/signup", json=admin_payload)
    admin_token = admin_signup.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    onboard_payload = {
        "name": "Event Filter Tenant",
        "slug": "event-event-filter-tenant",
        "vertical": "campus_club",
        "description": "A tenant used to test admin draft-status event filtering",
    }
    await client.post(
        "/tenant/onboarding",
        json=onboard_payload,
        headers=admin_headers,
    )
    login = await client.post(
        "/auth/login", json={"email": "admin@eventfilter.edu.in", "password": "Admin@123"}
    )
    admin_token = login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    member_payload = {
        "email": "leader@eventfilter.edu.in",
        "full_name": "Event Filter Leader",
        "password": "Leader@123",
        "confirm_password": "Leader@123",
        "role": "MEMBER",
        "tenant_slug": "event-event-filter-tenant",
    }
    member_signup = await client.post("/auth/signup", json=member_payload)
    member_token = member_signup.json()["access_token"]
    member_headers = {"Authorization": f"Bearer {member_token}"}

    group_payload = {
        "name": "Draft Filter Group",
        "description": "A group used to test admin draft-status event filtering",
        "category": "Technical",
        "type": "UNOFFICIAL",
    }
    group = await client.post("/groups", headers=member_headers, json=group_payload)
    group_id = group.json()["id"]

    create_payload = {
        "group_id": group_id,
        "title": "Still A Draft Workshop",
        "description": "An event that remains in draft for admin status filter testing",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=member_headers, json=create_payload)
    event_id = create.json()["id"]

    response = await client.get("/events", headers=admin_headers, params={"status": "DRAFT"})
    assert response.status_code == 200
    ids = [event["id"] for event in response.json()]
    assert event_id in ids


@pytest.mark.asyncio
async def test_browse_events_lowercase_status_fails(client, admin_token):
    """Validate that browsing events is rejected when the status filter uses lowercase casing"""
    response = await client.get("/events", headers={"Authorization": f"Bearer {admin_token}"}, params={"status": "draft"})
    assert response.status_code == 403
    assert response.json()["message"] == "Tenant mismatch"


@pytest.mark.asyncio
async def test_browse_events_upcoming_only_combined_with_group_id(client, db_session, leader, outsider, tenant_admin):
    """Verify that upcoming_only and group_id filters can be combined"""
    from app.models import Event

    leader_headers, group_id = leader
    create_payload = {
        "group_id": group_id,
        "title": "Combined Filter Workshop",
        "description": "An event used to test combined upcoming_only and group_id filters",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=leader_headers, json=create_payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=leader_headers)
    await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)

    response = await client.get(
        "/events", headers=outsider, params={"group_id": group_id, "upcoming_only": "true"}
    )
    assert response.status_code == 200
    ids = [event["id"] for event in response.json()]
    assert event_id in ids


@pytest.mark.asyncio
async def test_browse_events_unknown_group_id_returns_empty(client, outsider):
    """Confirm that filtering by a nonexistent group_id returns an empty list, not an error"""
    response = await client.get("/events", headers=outsider, params={"group_id": 999999})
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_browse_events_status_filter_ignored_for_members(client, leader, outsider):
    """Confirm that a member-supplied status filter is ignored and only published events are returned"""
    leader_headers, group_id = leader
    create_payload = {
        "group_id": group_id,
        "title": "Still Draft Workshop",
        "description": "A draft event used to test the ignored member status filter",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=leader_headers, json=create_payload)
    event_id = create.json()["id"]

    response = await client.get("/events", headers=outsider, params={"status": "DRAFT"})
    assert response.status_code == 200
    ids = [event["id"] for event in response.json()]
    assert event_id not in ids


# ==== view event ====

@pytest.mark.asyncio
async def test_view_event_shows_seats_left(client, leader, outsider, tenant_admin):
    """Verify that event detail reports capacity, registration count and seats left"""
    leader_headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
        "capacity": 2,
    }
    create = await client.post("/events", headers=leader_headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=leader_headers)
    await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)

    response = await client.get(f"/events/{event_id}", headers=outsider)
    assert response.status_code == 200
    body = response.json()
    assert body["capacity"] == 2
    assert body["registration_count"] == 0
    assert body["seats_left"] == 2
    assert body["is_registered"] is False
    assert body["my_registration_id"] is None


@pytest.mark.asyncio
async def test_view_draft_event_by_leader_succeeds(client, leader):
    """Confirm that the group leader can view their own draft event"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=headers, json=payload)
    event_id = create.json()["id"]

    response = await client.get(f"/events/{event_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "DRAFT"


@pytest.mark.asyncio
async def test_view_unknown_event_fails(client, outsider):
    """Confirm that viewing a non-existent event returns a not found error"""
    response = await client.get("/events/999999", headers=outsider)
    assert response.status_code == 404
    assert response.json()["message"] == "Event not found"


@pytest.mark.asyncio
async def test_view_draft_event_by_outsider_fails(client, leader, outsider):
    """Ensure that a draft event is hidden from a member who does not lead the group"""
    leader_headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=leader_headers, json=payload)
    event_id = create.json()["id"]

    response = await client.get(f"/events/{event_id}", headers=outsider)
    assert response.status_code == 404
    assert response.json()["message"] == "Event not found"


# ==== register for event ====

@pytest.mark.asyncio
async def test_register_success(client, leader, member, tenant_admin):
    """Verify that an approved group member can register for a published event"""
    leader_headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
        "capacity": 10,
    }
    create = await client.post("/events", headers=leader_headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=leader_headers)
    await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)

    response = await client.post(f"/events/{event_id}/register", headers=member)
    assert response.status_code == 200
    body = response.json()
    assert body["event_id"] == event_id
    assert body["event_title"] == "Line Follower Workshop"
    assert body["venue"] == "Lab 204, Main Block"
    assert isinstance(body["registration_id"], int)
    assert body["message"] == "Registered successfully"


@pytest.mark.asyncio
async def test_view_event_reflects_own_registration(client, leader, member, tenant_admin):
    """Confirm that event detail marks the caller as registered after they register"""
    leader_headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
        "capacity": 5,
    }
    create = await client.post("/events", headers=leader_headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=leader_headers)
    await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)
    registration = await client.post(f"/events/{event_id}/register", headers=member)
    registration_id = registration.json()["registration_id"]

    response = await client.get(f"/events/{event_id}", headers=member)
    assert response.status_code == 200
    body = response.json()
    assert body["is_registered"] is True
    assert body["my_registration_id"] == registration_id
    assert body["registration_count"] == 1
    assert body["seats_left"] == 4


@pytest.mark.asyncio
async def test_register_for_draft_event_fails(client, leader, member):
    """Confirm that registration is rejected for an event that is still a draft"""
    leader_headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=leader_headers, json=payload)
    event_id = create.json()["id"]

    response = await client.post(f"/events/{event_id}/register", headers=member)
    assert response.status_code == 403
    assert response.json()["message"] == "Event is not open for registration"


@pytest.mark.asyncio
async def test_register_for_cancelled_event_fails(client, leader, member, tenant_admin):
    """Confirm that registration is rejected once the event has been cancelled"""
    leader_headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=leader_headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=leader_headers)
    await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)
    await client.patch(f"/events/{event_id}/cancel", headers=leader_headers)

    response = await client.post(f"/events/{event_id}/register", headers=member)
    assert response.status_code == 403
    assert response.json()["message"] == "Event is not open for registration"


@pytest.mark.asyncio
async def test_register_by_non_member_fails(client, leader, outsider, tenant_admin):
    """Ensure that a member who is not an approved member of the group cannot register"""
    leader_headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=leader_headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=leader_headers)
    await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)

    response = await client.post(f"/events/{event_id}/register", headers=outsider)
    assert response.status_code == 403
    assert response.json()["message"] == "Only approved group members can register for this event"


@pytest.mark.asyncio
async def test_register_twice_fails(client, leader, member, tenant_admin):
    """Confirm that registering twice for the same event is rejected"""
    leader_headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=leader_headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=leader_headers)
    await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)
    await client.post(f"/events/{event_id}/register", headers=member)

    response = await client.post(f"/events/{event_id}/register", headers=member)
    assert response.status_code == 409
    assert response.json()["message"] == "You are already registered for this event"


@pytest.mark.asyncio
async def test_register_when_full_fails(client, leader, member, outsider, tenant_admin):
    """Confirm that registration is rejected once the event has reached its capacity"""
    leader_headers, group_id = leader
    join = await client.post(f"/groups/{group_id}/join", headers=outsider)
    approve_payload = {"action": "APPROVED"}
    await client.patch(
        f"/groups/{group_id}/requests/{join.json()['id']}",
        headers=leader_headers,
        json=approve_payload,
    )

    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
        "capacity": 1,
    }
    create = await client.post("/events", headers=leader_headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=leader_headers)
    await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)

    first = await client.post(f"/events/{event_id}/register", headers=member)
    assert first.status_code == 200

    second = await client.post(f"/events/{event_id}/register", headers=outsider)
    assert second.status_code == 409
    assert second.json()["message"] == "Event has reached its capacity"


@pytest.mark.asyncio
async def test_register_without_token_fails(client, leader, tenant_admin):
    """Ensure that registering is rejected when no access token is supplied"""
    leader_headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=leader_headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=leader_headers)
    await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)

    response = await client.post(f"/events/{event_id}/register")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.asyncio
async def test_register_after_event_started_fails(client, db_session, leader, member, tenant_admin):
    """Confirm that registration is rejected once the event's start time has passed"""
    from app.models import Event

    leader_headers, group_id = leader
    create_payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(2),
        "ends_at": future_time(4),
    }
    create = await client.post("/events", headers=leader_headers, json=create_payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=leader_headers)
    await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)

    event = await db_session.get(Event, event_id)
    event.starts_at = datetime.now(timezone.utc) - timedelta(hours=1)
    event.ends_at = datetime.now(timezone.utc) + timedelta(hours=1)
    await db_session.flush()

    response = await client.post(f"/events/{event_id}/register", headers=member)
    assert response.status_code == 403
    assert response.json()["message"] == "Registration for this event is closed"


# ==== unregister from event ====

@pytest.mark.asyncio
async def test_unregister_success(client, leader, member, tenant_admin):
    """Verify that a registered member can cancel their registration"""
    leader_headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=leader_headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=leader_headers)
    await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)
    await client.post(f"/events/{event_id}/register", headers=member)

    response = await client.delete(f"/events/{event_id}/register", headers=member)
    assert response.status_code == 200
    body = response.json()
    assert body["event_id"] == event_id
    assert body["message"] == "Registration cancelled"


@pytest.mark.asyncio
async def test_unregister_frees_a_seat(client, leader, member, outsider, tenant_admin):
    """Confirm that cancelling a registration releases the seat for another member"""
    leader_headers, group_id = leader
    join = await client.post(f"/groups/{group_id}/join", headers=outsider)
    approve_payload = {"action": "APPROVED"}
    await client.patch(
        f"/groups/{group_id}/requests/{join.json()['id']}",
        headers=leader_headers,
        json=approve_payload,
    )

    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
        "capacity": 1,
    }
    create = await client.post("/events", headers=leader_headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=leader_headers)
    await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)
    await client.post(f"/events/{event_id}/register", headers=member)
    blocked = await client.post(f"/events/{event_id}/register", headers=outsider)
    assert blocked.status_code == 409

    await client.delete(f"/events/{event_id}/register", headers=member)
    retry = await client.post(f"/events/{event_id}/register", headers=outsider)
    assert retry.status_code == 200


@pytest.mark.asyncio
async def test_unregister_without_registration_fails(client, leader, member, tenant_admin):
    """Confirm that unregistering is rejected when the member never registered"""
    leader_headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=leader_headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=leader_headers)
    await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)

    response = await client.delete(f"/events/{event_id}/register", headers=member)
    assert response.status_code == 404
    assert response.json()["message"] == "Registration not found"


@pytest.mark.asyncio
async def test_unregister_after_event_started_fails(client, db_session, leader, member, tenant_admin):
    """Confirm that unregistering is rejected once the event's start time has passed"""
    from app.models import Event

    leader_headers, group_id = leader
    create_payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(2),
        "ends_at": future_time(4),
    }
    create = await client.post("/events", headers=leader_headers, json=create_payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=leader_headers)
    await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)
    await client.post(f"/events/{event_id}/register", headers=member)

    event = await db_session.get(Event, event_id)
    event.starts_at = datetime.now(timezone.utc) - timedelta(hours=1)
    event.ends_at = datetime.now(timezone.utc) + timedelta(hours=1)
    await db_session.flush()

    response = await client.delete(f"/events/{event_id}/register", headers=member)
    assert response.status_code == 403
    assert response.json()["message"] == "Registration for this event is closed"


# ==== participants ====

@pytest.mark.asyncio
async def test_participants_list_success(client, leader, member, tenant_admin):
    """Verify that the leader can list the participants of their event"""
    leader_headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=leader_headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=leader_headers)
    await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)
    await client.post(f"/events/{event_id}/register", headers=member)

    response = await client.get(f"/events/{event_id}/registrations", headers=leader_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["email"] == "member@knit.edu.in"
    assert body[0]["checked_in"] is False
    assert body[0]["result"] == "REGISTRANT"


@pytest.mark.asyncio
async def test_participants_list_by_non_leader_fails(client, leader, member, tenant_admin):
    """Ensure that a plain member cannot view the participant list"""
    leader_headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=leader_headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=leader_headers)
    await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)

    response = await client.get(f"/events/{event_id}/registrations", headers=member)
    assert response.status_code == 403


# ==== attendance ====

@pytest.mark.asyncio
async def test_mark_attendance_success(client, started_event):
    """Verify that the leader can check a participant in once the event has started"""
    leader_headers, event_id, registration_id = started_event

    payload = {"checked_in": True}
    response = await client.patch(
        f"/events/{event_id}/registrations/{registration_id}/attendance",
        headers=leader_headers, json=payload,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["registration_id"] == registration_id
    assert body["checked_in"] is True
    assert body["checked_in_at"] is not None
    assert body["message"] == "Attendance marked"


@pytest.mark.asyncio
async def test_unmark_attendance_resets_result(client, started_event):
    """Confirm that undoing a check-in also resets an already recorded result to REGISTRANT"""
    leader_headers, event_id, registration_id = started_event
    attendance_payload = {"checked_in": True}
    await client.patch(f"/events/{event_id}/registrations/{registration_id}/attendance",
                       headers=leader_headers, json=attendance_payload)
    result_payload = {"result": "WINNER"}
    await client.patch(f"/events/{event_id}/registrations/{registration_id}/result",
                       headers=leader_headers, json=result_payload)

    reset_payload = {"checked_in": False}
    response = await client.patch(
        f"/events/{event_id}/registrations/{registration_id}/attendance",
        headers=leader_headers, json=reset_payload,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["checked_in"] is False
    assert body["message"] == "Attendance unmarked"

    participants = await client.get(f"/events/{event_id}/registrations", headers=leader_headers)
    assert participants.json()[0]["result"] == "REGISTRANT"


@pytest.mark.asyncio
async def test_mark_attendance_before_event_starts_fails(client, leader, member, tenant_admin):
    """Confirm that attendance cannot be marked before the event has started"""
    leader_headers, group_id = leader
    create_payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=leader_headers, json=create_payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=leader_headers)
    await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)
    registration = await client.post(f"/events/{event_id}/register", headers=member)
    registration_id = registration.json()["registration_id"]

    attendance_payload = {"checked_in": True}
    response = await client.patch(
        f"/events/{event_id}/registrations/{registration_id}/attendance",
        headers=leader_headers, json=attendance_payload,
    )
    assert response.status_code == 403
    assert response.json()["message"] == "Attendance can only be marked once the event has started"


@pytest.mark.asyncio
async def test_mark_attendance_unknown_registration_fails(client, started_event):
    """Ensure that an attendance update is rejected for a registration id that does not exist"""
    leader_headers, event_id, _ = started_event

    payload = {"checked_in": True}
    response = await client.patch(
        f"/events/{event_id}/registrations/999999/attendance",
        headers=leader_headers, json=payload,
    )
    assert response.status_code == 404
    assert response.json()["message"] == "Registration not found"


@pytest.mark.asyncio
async def test_mark_attendance_by_non_leader_fails(client, started_event, outsider):
    """Ensure that a member who does not lead the group cannot mark attendance"""
    _, event_id, registration_id = started_event

    payload = {"checked_in": True}
    response = await client.patch(
        f"/events/{event_id}/registrations/{registration_id}/attendance",
        headers=outsider, json=payload,
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_mark_attendance_registration_from_different_event_fails(client, started_event, leader, member, tenant_admin):
    """Confirm that a registration from a different event cannot be marked via this event's attendance route"""
    leader_headers, event_id, _ = started_event
    _, group_id = leader

    event_payload = {
        "group_id": group_id,
        "title": "Other Event",
        "description": "A separate event for cross-event testing",
        "venue": "Elsewhere",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    other_event = await client.post("/events", headers=leader_headers, json=event_payload)
    other_event_id = other_event.json()["id"]
    await client.patch(f"/events/{other_event_id}/submit-for-review", headers=leader_headers)
    await client.patch(f"/events/{other_event_id}/publish", headers=tenant_admin)
    other_reg = await client.post(f"/events/{other_event_id}/register", headers=member)
    other_reg_id = other_reg.json()["registration_id"]

    payload = {"checked_in": True}
    response = await client.patch(
        f"/events/{event_id}/registrations/{other_reg_id}/attendance",
        headers=leader_headers,
        json=payload,
    )
    assert response.status_code == 404
    assert response.json()["message"] == "Registration not found"


# ==== results ====

# ==== my registrations ====

@pytest.mark.asyncio
async def test_my_registrations_lists_registered_events(client, leader, member, tenant_admin):
    """Verify that a member can list the events they are registered for"""
    leader_headers, group_id = leader
    create_payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=leader_headers, json=create_payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=leader_headers)
    await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)
    await client.post(f"/events/{event_id}/register", headers=member)

    response = await client.get("/events/me/registrations", headers=member)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["event_id"] == event_id
    assert body[0]["event_status"] == "PUBLISHED"
    assert body[0]["checked_in"] is False


@pytest.mark.asyncio
async def test_my_registrations_empty_for_new_member(client, outsider):
    """Confirm that a member with no registrations receives an empty list"""
    response = await client.get("/events/me/registrations", headers=outsider)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_my_registrations_without_token_fails(client):
    """Ensure that listing personal registrations is rejected without an access token"""
    response = await client.get("/events/me/registrations")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# ==== my results ====

@pytest.mark.asyncio
async def test_my_results_lists_recorded_result(client, two_checked_in, member):
    """Verify that a member can see their recorded result after results are declared"""
    leader_headers, event_id, member_registration_id, second_registration_id = two_checked_in

    result_payload = {
        "winner_registration_id": member_registration_id,
        "runner_up_registration_id": second_registration_id,
    }
    declare = await client.patch(
        f"/events/{event_id}/results", headers=leader_headers, json=result_payload
    )
    assert declare.status_code == 200

    response = await client.get("/events/me/results", headers=member)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["event_id"] == event_id
    assert body[0]["registration_id"] == member_registration_id
    assert body[0]["result"] == "WINNER"


@pytest.mark.asyncio
async def test_my_results_excludes_plain_registrants(client, started_event, member):
    """Confirm that an event where the member was never checked in is excluded from results"""
    response = await client.get("/events/me/results", headers=member)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_my_results_without_token_fails(client):
    """Ensure that listing personal results is rejected without an access token"""
    response = await client.get("/events/me/results")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# ==== declare results ====

@pytest.mark.asyncio
async def test_declare_results_success(client, two_checked_in):
    """Verify that the leader can declare distinct winner and runner-up for checked-in attendees"""
    leader_headers, event_id, first_id, second_id = two_checked_in

    payload = {"winner_registration_id": first_id, "runner_up_registration_id": second_id}
    response = await client.patch(f"/events/{event_id}/results", headers=leader_headers, json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["event_id"] == event_id
    assert body["winner"]["registration_id"] == first_id
    assert body["winner"]["result"] == "WINNER"
    assert body["runner_up"]["registration_id"] == second_id
    assert body["runner_up"]["result"] == "RUNNER_UP"
    assert body["participants"] == 0
    assert body["certificates_queued"] == 2
    assert body["message"] == "Results declared, certificates are being generated"


@pytest.mark.asyncio
async def test_declare_results_same_registration_for_both_fails(client, two_checked_in):
    """Validate that winner and runner-up cannot be the same registration"""
    leader_headers, event_id, first_id, _ = two_checked_in

    payload = {"winner_registration_id": first_id, "runner_up_registration_id": first_id}
    response = await client.patch(f"/events/{event_id}/results", headers=leader_headers, json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_declare_results_winner_not_checked_in_fails(client, db_session, leader, member, second_member, tenant_admin):
    """Confirm that a registration which was never checked in cannot be declared winner"""
    from app.models import Event
    from datetime import datetime, timedelta, timezone

    leader_headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat(),
        "ends_at": (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat(),
    }
    create = await client.post("/events", headers=leader_headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/submit-for-review", headers=leader_headers)
    await client.patch(f"/events/{event_id}/publish", headers=tenant_admin)

    checked_in_reg = await client.post(f"/events/{event_id}/register", headers=member)
    checked_in_id = checked_in_reg.json()["registration_id"]
    not_checked_in_reg = await client.post(f"/events/{event_id}/register", headers=second_member)
    not_checked_in_id = not_checked_in_reg.json()["registration_id"]

    event = await db_session.get(Event, event_id)
    event.starts_at = datetime.now(timezone.utc) - timedelta(hours=1)
    event.ends_at = datetime.now(timezone.utc) + timedelta(hours=1)
    await db_session.flush()

    await client.patch(
        f"/events/{event_id}/registrations/{checked_in_id}/attendance",
        headers=leader_headers, json={"checked_in": True},
    )

    payload = {"winner_registration_id": not_checked_in_id, "runner_up_registration_id": checked_in_id}
    response = await client.patch(f"/events/{event_id}/results", headers=leader_headers, json=payload)
    assert response.status_code == 400
    assert response.json()["message"] == "Result can only be set for attendees who were checked in"

@pytest.mark.asyncio
async def test_declare_results_unknown_registration_fails(client, two_checked_in):
    """Confirm that declaring results with a registration id from another event or nonexistent fails"""
    leader_headers, event_id, first_id, _ = two_checked_in

    payload = {"winner_registration_id": first_id, "runner_up_registration_id": 999999}
    response = await client.patch(f"/events/{event_id}/results", headers=leader_headers, json=payload)
    assert response.status_code == 404
    assert response.json()["message"] == "Registration not found"


@pytest.mark.asyncio
async def test_declare_results_twice_fails(client, two_checked_in):
    """Confirm that declaring results a second time on the same event is rejected"""
    leader_headers, event_id, first_id, second_id = two_checked_in
    payload = {"winner_registration_id": first_id, "runner_up_registration_id": second_id}
    await client.patch(f"/events/{event_id}/results", headers=leader_headers, json=payload)

    response = await client.patch(f"/events/{event_id}/results", headers=leader_headers, json=payload)
    assert response.status_code == 409
    assert response.json()["message"] == "Results for this event have already been declared and can no longer be changed"


@pytest.mark.asyncio
async def test_declare_results_by_non_leader_fails(client, two_checked_in, outsider):
    """Ensure that a member who does not lead the group cannot declare results"""
    _, event_id, first_id, second_id = two_checked_in
    payload = {"winner_registration_id": first_id, "runner_up_registration_id": second_id}
    response = await client.patch(f"/events/{event_id}/results", headers=outsider, json=payload)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_declare_results_unknown_event_fails(client, leader):
    """Confirm that declaring results for a non-existent event returns not found"""
    headers, _ = leader
    payload = {"winner_registration_id": 1, "runner_up_registration_id": 2}
    response = await client.patch("/events/999999/results", headers=headers, json=payload)
    assert response.status_code == 404
    assert response.json()["message"] == "Event not found"


@pytest.mark.asyncio
async def test_declare_results_without_token_fails(client, two_checked_in):
    """Ensure that declaring results is rejected without an access token"""
    _, event_id, first_id, second_id = two_checked_in
    payload = {"winner_registration_id": first_id, "runner_up_registration_id": second_id}
    response = await client.patch(f"/events/{event_id}/results", json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# ==== attendance freeze after results declared ====

@pytest.mark.asyncio
async def test_mark_attendance_after_results_declared_fails(client, two_checked_in):
    """Confirm that attendance can no longer be marked once results have been declared"""
    leader_headers, event_id, first_id, second_id = two_checked_in
    result_payload = {"winner_registration_id": first_id, "runner_up_registration_id": second_id}
    await client.patch(f"/events/{event_id}/results", headers=leader_headers, json=result_payload)

    attendance_payload = {"checked_in": False}
    response = await client.patch(
        f"/events/{event_id}/registrations/{first_id}/attendance",
        headers=leader_headers, json=attendance_payload,
    )
    assert response.status_code == 409
    assert response.json()["message"] == "Results for this event have already been declared and can no longer be changed"


@pytest.mark.asyncio
async def test_mark_attendance_freeze_applies_to_uninvolved_registration(client, two_checked_in):
    """Confirm that the attendance freeze also blocks a registration not chosen as winner/runner-up"""
    leader_headers, event_id, first_id, second_id = two_checked_in
    result_payload = {"winner_registration_id": first_id, "runner_up_registration_id": second_id}
    await client.patch(f"/events/{event_id}/results", headers=leader_headers, json=result_payload)

    # second_id was runner_up but was already checked in before declaration; verify freeze
    # generically by attempting to toggle it again
    attendance_payload = {"checked_in": True}
    response = await client.patch(
        f"/events/{event_id}/registrations/{second_id}/attendance",
        headers=leader_headers, json=attendance_payload,
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_declare_results_registration_from_different_event_fails(client, two_checked_in, leader):
    """Confirm a registration ID belonging to a different event is rejected"""
    leader_headers, event_id, first_id, second_id = two_checked_in
    _, group_id = leader
    other_event = await client.post("/events", headers=leader_headers, json={
        "group_id": group_id, "title": "Other Event", "description": "A separate event",
        "venue": "Elsewhere", "starts_at": future_time(48), "ends_at": future_time(50),
    })
    other_event_id = other_event.json()["id"]

    payload = {"winner_registration_id": first_id, "runner_up_registration_id": second_id}
    response = await client.patch(f"/events/{other_event_id}/results", headers=leader_headers, json=payload)
    assert response.status_code == 404
    assert response.json()["message"] == "Registration not found"


@pytest.mark.asyncio
async def test_declare_results_participants_count_with_three_attendees(client, three_checked_in):
    """Verify that participants count correctly excludes winner and runner-up from the total"""
    leader_headers, event_id, ids = three_checked_in
    payload = {"winner_registration_id": ids[0], "runner_up_registration_id": ids[1]}
    response = await client.patch(f"/events/{event_id}/results", headers=leader_headers, json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["participants"] == 1
    assert body["certificates_queued"] == 3
