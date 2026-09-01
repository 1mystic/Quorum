import pytest
from datetime import datetime, timedelta, timezone


def future_time(hours: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


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
async def second_member(client, seed_tenant, leader):
    """Another approved member of the leader's group, distinct from `member`."""
    leader_headers, group_id = leader
    payload = {
        "email": "notif-second@knit.edu.in",
        "full_name": "Second Member",
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
async def started_event(client, db_session, leader, member):
    """A published event whose window has already started, with the member registered."""
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
    await client.patch(f"/events/{event_id}/publish", headers=leader_headers)
    registration = await client.post(f"/events/{event_id}/register", headers=member)
    registration_id = registration.json()["registration_id"]

    event = await db_session.get(Event, event_id)
    event.starts_at = datetime.now(timezone.utc) - timedelta(hours=1)
    event.ends_at = datetime.now(timezone.utc) + timedelta(hours=1)
    await db_session.flush()

    return leader_headers, event_id, registration_id


@pytest.fixture
async def two_checked_in(client, db_session, leader, member, second_member):
    """Two members registered and checked in, event already started."""
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
    await client.patch(f"/events/{event_id}/publish", headers=leader_headers)

    first = await client.post(f"/events/{event_id}/register", headers=member)
    first_registration_id = first.json()["registration_id"]
    second = await client.post(f"/events/{event_id}/register", headers=second_member)
    second_registration_id = second.json()["registration_id"]

    event = await db_session.get(Event, event_id)
    event.starts_at = datetime.now(timezone.utc) - timedelta(hours=1)
    event.ends_at = datetime.now(timezone.utc) + timedelta(hours=1)
    await db_session.flush()

    attendance_payload = {"checked_in": True}
    await client.patch(
        f"/events/{event_id}/registrations/{first_registration_id}/attendance",
        headers=leader_headers,
        json=attendance_payload,
    )
    await client.patch(
        f"/events/{event_id}/registrations/{second_registration_id}/attendance",
        headers=leader_headers,
        json=attendance_payload,
    )
    return leader_headers, event_id, first_registration_id, second_registration_id


# ==== list notifications ====

@pytest.mark.asyncio
async def test_list_notifications_empty_for_new_member(client, outsider):
    """Verify that a member with no notifications gets an empty list"""
    response = await client.get("/notifications", headers=outsider)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_list_notifications_filter_by_type(client, leader, member):
    """Verify that filtering by type returns only notifications matching that type, not others"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Type filter event",
        "description": "An event used to test notification type filtering",
        "venue": "Lab 204",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/publish", headers=headers)
    await client.post(f"/events/{event_id}/register", headers=member)


    response = await client.get(
        "/notifications", headers=member, params={"type": "JOIN_APPROVED"}
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["type"] == "JOIN_APPROVED"

    other_type_response = await client.get(
        "/notifications", headers=member, params={"type": "REGISTRATION_CONFIRMED"}
    )
    other_body = other_type_response.json()
    assert len(other_body) == 1
    assert other_body[0]["type"] == "REGISTRATION_CONFIRMED"


@pytest.mark.asyncio
async def test_list_notifications_filter_by_is_read(client, leader, member):
    """Verify that filtering by is_read returns only notifications matching that read state"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Notif filter event",
        "description": "An event used to test notification is_read filtering",
        "venue": "Lab 204",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/publish", headers=headers)
    await client.post(f"/events/{event_id}/register", headers=member)

    response = await client.get(
        "/notifications", headers=member, params={"is_read": False}
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) >= 1
    assert all(item["is_read"] is False for item in body)


@pytest.mark.asyncio
async def test_list_notifications_lowercase_type_filter_fails(client, member):
    """Validate that filtering by type is rejected when using lowercase casing"""
    response = await client.get(
        "/notifications", headers=member, params={"type": "join_approved"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_notifications_limit_zero_fails(client, member):
    """Validate that listing notifications is rejected when limit is below the minimum of 1"""
    response = await client.get("/notifications", headers=member, params={"limit": 0})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_notifications_limit_over_max_fails(client, member):
    """Validate that listing notifications is rejected when limit exceeds the maximum of 100"""
    response = await client.get("/notifications", headers=member, params={"limit": 101})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_notifications_offset_negative_fails(client, member):
    """Validate that listing notifications is rejected when offset is negative"""
    response = await client.get("/notifications", headers=member, params={"offset": -1})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_notifications_ordered_newest_first(client, db_session, leader, member):
    """Verify that notifications are returned with the most recently created one first"""
    from datetime import datetime, timedelta
    from app.models import Notification

    headers, group_id = leader
    first_payload = {
        "group_id": group_id,
        "title": "First notif event",
        "description": "The first event that triggers a notification",
        "venue": "Lab 204",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    first_create = await client.post("/events", headers=headers, json=first_payload)
    first_event_id = first_create.json()["id"]
    await client.patch(f"/events/{first_event_id}/publish", headers=headers)
    await client.post(f"/events/{first_event_id}/register", headers=member)

    second_payload = {
        "group_id": group_id,
        "title": "Second notif event",
        "description": "The second event that triggers a notification",
        "venue": "Lab 204",
        "starts_at": future_time(72),
        "ends_at": future_time(75),
    }
    second_create = await client.post("/events", headers=headers, json=second_payload)
    second_event_id = second_create.json()["id"]
    await client.patch(f"/events/{second_event_id}/publish", headers=headers)
    second_registration = await client.post(f"/events/{second_event_id}/register", headers=member)

    result = await db_session.execute(
        Notification.__table__.select().where(Notification.event_id == second_event_id)
    )
    second_notification = result.first()
    notification = await db_session.get(Notification, second_notification.id)
    notification.created_at = datetime.now() + timedelta(seconds=5)
    await db_session.flush()

    response = await client.get("/notifications", headers=member)
    assert response.status_code == 200
    body = response.json()
    event_ids_in_order = [item["event_id"] for item in body]
    assert event_ids_in_order.index(second_event_id) < event_ids_in_order.index(first_event_id)

@pytest.mark.asyncio
async def test_list_notifications_without_token_fails(client):
    """Ensure that listing notifications is rejected without an access token"""
    response = await client.get("/notifications")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# ==== unread count ====

@pytest.mark.asyncio
async def test_unread_count_zero_for_new_member(client, outsider):
    """Verify that a member with no notifications has an unread count of zero"""
    response = await client.get("/notifications/unread-count", headers=outsider)
    assert response.status_code == 200
    assert response.json()["count"] == 0


@pytest.mark.asyncio
async def test_unread_count_increases_after_registration(client, leader, member):
    """Verify that unread-count increases after a REGISTRATION_CONFIRMED notification fires"""
    before = await client.get("/notifications/unread-count", headers=member)
    initial_count = before.json()["count"]

    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Unread count event",
        "description": "An event used to test the unread notification count",
        "venue": "Lab 204",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/publish", headers=headers)
    await client.post(f"/events/{event_id}/register", headers=member)

    after = await client.get("/notifications/unread-count", headers=member)
    assert after.json()["count"] == initial_count + 1


@pytest.mark.asyncio
async def test_unread_count_without_token_fails(client):
    """Ensure that requesting the unread count is rejected without an access token"""
    response = await client.get("/notifications/unread-count")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# ==== read-all ====

@pytest.mark.asyncio
async def test_mark_all_notifications_read_success(client, leader, member):
    """Verify that read-all marks all unread notifications as read and reports the count updated"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Mark all read event",
        "description": "An event used to test marking all notifications read",
        "venue": "Lab 204",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/publish", headers=headers)
    await client.post(f"/events/{event_id}/register", headers=member)

    response = await client.post("/notifications/read-all", headers=member)
    assert response.status_code == 200
    body = response.json()
    assert body["updated"] >= 1
    assert body["message"] == "All notifications marked as read"

    count = await client.get("/notifications/unread-count", headers=member)
    assert count.json()["count"] == 0

    listed = await client.get("/notifications", headers=member)
    assert all(item["is_read"] is True for item in listed.json())


@pytest.mark.asyncio
async def test_mark_all_notifications_read_zero_when_none_unread(client, seed_tenant):
    """Confirm that read-all reports zero updated when there are no unread notifications"""
    payload = {
        "email": "freshmember@knit.edu.in",
        "full_name": "Fresh Member",
        "password": "Test@1234",
        "confirm_password": "Test@1234",
        "role": "MEMBER",
        "tenant_slug": seed_tenant.slug,
    }
    signup = await client.post("/auth/signup", json=payload)
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    response = await client.post("/notifications/read-all", headers=headers)
    assert response.status_code == 200
    assert response.json()["updated"] == 0


@pytest.mark.asyncio
async def test_mark_all_notifications_read_without_token_fails(client):
    """Ensure that read-all is rejected without an access token"""
    response = await client.post("/notifications/read-all")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# ==== mark single notification read ====

@pytest.mark.asyncio
async def test_mark_notification_read_success(client, leader, member):
    """Verify that a member can mark their own notification as read"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Mark single read event",
        "description": "An event used to test marking a single notification read",
        "venue": "Lab 204",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/publish", headers=headers)
    await client.post(f"/events/{event_id}/register", headers=member)

    listed = await client.get("/notifications", headers=member)
    notification_id = listed.json()[0]["id"]

    response = await client.patch(f"/notifications/{notification_id}/read", headers=headers if False else member)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == notification_id
    assert body["is_read"] is True
    assert body["message"] == "Notification marked as read"


@pytest.mark.asyncio
async def test_mark_notification_read_unknown_id_fails(client, member):
    """Confirm that marking a nonexistent notification as read returns not found"""
    response = await client.patch("/notifications/999999/read", headers=member)
    assert response.status_code == 404
    assert response.json()["message"] == "Notification not found"


@pytest.mark.asyncio
async def test_mark_notification_read_belonging_to_another_member_fails(client, leader, member, outsider):
    """Ensure that a member cannot mark another member's notification as read"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Cross member read event",
        "description": "An event used to test cross-member notification access",
        "venue": "Lab 204",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/publish", headers=headers)
    await client.post(f"/events/{event_id}/register", headers=member)

    listed = await client.get("/notifications", headers=member)
    notification_id = listed.json()[0]["id"]

    response = await client.patch(f"/notifications/{notification_id}/read", headers=outsider)
    assert response.status_code == 404
    assert response.json()["message"] == "Notification not found"


@pytest.mark.asyncio
async def test_mark_already_read_notification_succeeds_idempotently(client, leader, member):
    """Confirm that marking an already-read notification as read again succeeds without error"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Double read event",
        "description": "An event used to test double-marking a notification read",
        "venue": "Lab 204",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/publish", headers=headers)
    await client.post(f"/events/{event_id}/register", headers=member)

    listed = await client.get("/notifications", headers=member)
    notification_id = listed.json()[0]["id"]

    first = await client.patch(f"/notifications/{notification_id}/read", headers=member)
    assert first.status_code == 200
    second = await client.patch(f"/notifications/{notification_id}/read", headers=member)
    assert second.status_code == 200
    assert second.json()["is_read"] is True


@pytest.mark.asyncio
async def test_mark_notification_read_without_token_fails(client, leader, member):
    """Ensure that marking a notification read is rejected without an access token"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "No token read event",
        "description": "An event used to test unauthenticated notification access",
        "venue": "Lab 204",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/publish", headers=headers)
    await client.post(f"/events/{event_id}/register", headers=member)

    listed = await client.get("/notifications", headers=member)
    notification_id = listed.json()[0]["id"]

    response = await client.patch(f"/notifications/{notification_id}/read")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# ==== JOIN_APPROVED / JOIN_REJECTED triggers ====

@pytest.mark.asyncio
async def test_join_approved_creates_notification(client, leader, outsider):
    """Verify that approving a join request creates a JOIN_APPROVED notification with the group name"""
    leader_headers, group_id = leader
    join = await client.post(f"/groups/{group_id}/join", headers=outsider)
    action_payload = {"action": "APPROVED"}
    await client.patch(
        f"/groups/{group_id}/requests/{join.json()['id']}", headers=leader_headers, json=action_payload
    )

    response = await client.get("/notifications", headers=outsider)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["type"] == "JOIN_APPROVED"
    assert body[0]["message"] == "Your request to join Robotics Group was approved"
    assert body[0]["group_id"] == group_id
    assert body[0]["event_id"] is None
    assert body[0]["is_read"] is False


@pytest.mark.asyncio
async def test_join_rejected_creates_notification(client, leader, outsider):
    """Verify that rejecting a join request creates a JOIN_REJECTED notification with the group name"""
    leader_headers, group_id = leader
    join = await client.post(f"/groups/{group_id}/join", headers=outsider)
    action_payload = {"action": "REJECTED"}
    await client.patch(
        f"/groups/{group_id}/requests/{join.json()['id']}", headers=leader_headers, json=action_payload
    )

    response = await client.get("/notifications", headers=outsider)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["type"] == "JOIN_REJECTED"
    assert body[0]["message"] == "Your request to join Robotics Group was not approved"


@pytest.mark.asyncio
async def test_join_approved_notification_not_visible_to_leader(client, leader, outsider):
    """Confirm that the JOIN_APPROVED notification is created for the joiner, not the approving leader"""
    leader_headers, group_id = leader
    join = await client.post(f"/groups/{group_id}/join", headers=outsider)
    action_payload = {"action": "APPROVED"}
    await client.patch(
        f"/groups/{group_id}/requests/{join.json()['id']}", headers=leader_headers, json=action_payload
    )

    response = await client.get("/notifications", headers=leader_headers)
    assert response.status_code == 200
    assert response.json() == []


# ==== REGISTRATION_CONFIRMED trigger ====

@pytest.mark.asyncio
async def test_registration_creates_notification(client, leader, member):
    """Verify that registering for an event creates a REGISTRATION_CONFIRMED notification"""
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
    await client.patch(f"/events/{event_id}/publish", headers=headers)
    await client.post(f"/events/{event_id}/register", headers=member)

    response = await client.get(
        "/notifications", headers=member, params={"type": "REGISTRATION_CONFIRMED"}
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["message"] == "You are registered for Line Follower Workshop"
    assert body[0]["group_id"] == group_id
    assert body[0]["event_id"] == event_id


# ==== RESULT_POSTED trigger ====

@pytest.mark.asyncio
async def test_result_posted_notification_visible_to_registrant(client, member, two_checked_in):
    """Verify that the RESULT_POSTED notification appears for the participant who received the result"""
    leader_headers, event_id, winner_reg_id, runner_up_reg_id = two_checked_in
    result_payload = {
        "winner_registration_id": winner_reg_id,
        "runner_up_registration_id": runner_up_reg_id,
    }
    await client.patch(f"/events/{event_id}/results", headers=leader_headers, json=result_payload)

    response = await client.get(
        "/notifications", headers=member, params={"type": "RESULT_POSTED"}
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["message"] == "Your result for Line Follower Workshop is now available: WINNER"
    assert body[0]["event_id"] == event_id


@pytest.mark.asyncio
async def test_result_registrant_value_does_not_create_notification(client, member, two_checked_in):
    """Confirm that declaring results posts notifications for checked-in participants"""
    leader_headers, event_id, winner_reg_id, runner_up_reg_id = two_checked_in
    result_payload = {
        "winner_registration_id": winner_reg_id,
        "runner_up_registration_id": runner_up_reg_id,
    }
    await client.patch(f"/events/{event_id}/results", headers=leader_headers, json=result_payload)

    response = await client.get(
        "/notifications", headers=member, params={"type": "RESULT_POSTED"}
    )
    assert response.status_code == 200
    assert len(response.json()) == 1

@pytest.mark.asyncio
async def test_list_notifications_pagination_slices_correctly(client, db_session, leader, member):
    """Verify that limit and offset correctly slice notifications in created_at order"""
    from datetime import datetime, timedelta
    from app.models import Notification

    headers, group_id = leader
    event_ids = []
    for i in range(3):
        payload = {
            "group_id": group_id,
            "title": f"Pagination event {i}",
            "description": f"Event number {i} used to test notification pagination",
            "venue": "Lab 204",
            "starts_at": future_time(48 + i),
            "ends_at": future_time(50 + i),
        }
        create = await client.post("/events", headers=headers, json=payload)
        event_id = create.json()["id"]
        event_ids.append(event_id)
        await client.patch(f"/events/{event_id}/publish", headers=headers)
        await client.post(f"/events/{event_id}/register", headers=member)

    for i, event_id in enumerate(event_ids):
        result = await db_session.execute(
            Notification.__table__.select().where(Notification.event_id == event_id)
        )
        row = result.first()
        notification = await db_session.get(Notification, row.id)
        notification.created_at = datetime.now() + timedelta(seconds=(i + 1) * 5)
        await db_session.flush()

    
    response = await client.get(
        "/notifications", headers=member, params={"limit": 1, "offset": 1}
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["event_id"] == event_ids[1]

@pytest.mark.asyncio
async def test_mark_all_notifications_read_does_not_affect_other_members(client, leader, member, outsider):
    """Verify that read-all for one member does not mark another member's notifications as read"""
    leader_headers, group_id = leader
    join = await client.post(f"/groups/{group_id}/join", headers=outsider)
    action_payload = {"action": "APPROVED"}
    await client.patch(
        f"/groups/{group_id}/requests/{join.json()['id']}", headers=leader_headers, json=action_payload
    )

    await client.post("/notifications/read-all", headers=member)

    member_count = await client.get("/notifications/unread-count", headers=member)
    assert member_count.json()["count"] == 0

    outsider_count = await client.get("/notifications/unread-count", headers=outsider)
    assert outsider_count.json()["count"] == 1

@pytest.mark.asyncio
async def test_unread_count_decrements_by_one_after_single_read(client, leader, member):
    """Verify that marking a single notification as read decrements the unread count by exactly 1"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Single decrement event",
        "description": "An event used to test single-notification unread count decrement",
        "venue": "Lab 204",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/publish", headers=headers)
    await client.post(f"/events/{event_id}/register", headers=member)

    before = await client.get("/notifications/unread-count", headers=member)
    initial_count = before.json()["count"]
    assert initial_count >= 1

    listed = await client.get("/notifications", headers=member)
    notification_id = listed.json()[0]["id"]
    await client.patch(f"/notifications/{notification_id}/read", headers=member)

    after = await client.get("/notifications/unread-count", headers=member)
    assert after.json()["count"] == initial_count - 1

@pytest.mark.asyncio
async def test_join_approved_twice_does_not_duplicate_notification(client, leader, outsider):
    """Confirm that attempting to approve an already-handled request does not create a second notification"""
    leader_headers, group_id = leader
    join = await client.post(f"/groups/{group_id}/join", headers=outsider)
    action_payload = {"action": "APPROVED"}
    await client.patch(
        f"/groups/{group_id}/requests/{join.json()['id']}", headers=leader_headers, json=action_payload
    )
    second_attempt = await client.patch(
        f"/groups/{group_id}/requests/{join.json()['id']}", headers=leader_headers, json=action_payload
    )
    assert second_attempt.status_code == 403

    response = await client.get("/notifications", headers=outsider, params={"type": "JOIN_APPROVED"})
    assert len(response.json()) == 1

@pytest.mark.asyncio
async def test_declare_results_twice_does_not_create_duplicate_notifications(client, member, two_checked_in):
    """Confirm that declaring results twice is rejected and does not create duplicate notifications"""
    leader_headers, event_id, winner_reg_id, runner_up_reg_id = two_checked_in
    result_payload = {
        "winner_registration_id": winner_reg_id,
        "runner_up_registration_id": runner_up_reg_id,
    }
    first = await client.patch(f"/events/{event_id}/results", headers=leader_headers, json=result_payload)
    assert first.status_code == 200

    second = await client.patch(f"/events/{event_id}/results", headers=leader_headers, json=result_payload)
    assert second.status_code == 409

    response = await client.get("/notifications", headers=member, params={"type": "RESULT_POSTED"})
    assert len(response.json()) == 1

@pytest.mark.asyncio
async def test_registration_failure_does_not_create_notification(client, leader, member, outsider):
    """Confirm that a failed registration attempt (event full) does not create a notification"""
    leader_headers, group_id = leader
    join = await client.post(f"/groups/{group_id}/join", headers=outsider)
    approve_payload = {"action": "APPROVED"}
    await client.patch(
        f"/groups/{group_id}/requests/{join.json()['id']}", headers=leader_headers, json=approve_payload
    )

    payload = {
        "group_id": group_id,
        "title": "Full capacity event",
        "description": "An event used to test that failed registration creates no notification",
        "venue": "Lab 204",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
        "capacity": 1,
    }
    create = await client.post("/events", headers=leader_headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/publish", headers=leader_headers)
    await client.post(f"/events/{event_id}/register", headers=member)

    failed = await client.post(f"/events/{event_id}/register", headers=outsider)
    assert failed.status_code == 409

    response = await client.get(
        "/notifications", headers=outsider, params={"type": "REGISTRATION_CONFIRMED"}
    )
    assert response.json() == []

@pytest.mark.asyncio
async def test_list_notifications_combined_is_read_and_type_filters(client, leader, member):
    """Verify that is_read and type filters can be combined"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Combined filter event",
        "description": "An event used to test combined is_read and type filters",
        "venue": "Lab 204",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/publish", headers=headers)
    await client.post(f"/events/{event_id}/register", headers=member)

    response = await client.get(
        "/notifications", headers=member,
        params={"is_read": False, "type": "REGISTRATION_CONFIRMED"},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["is_read"] is False
    assert body[0]["type"] == "REGISTRATION_CONFIRMED"

@pytest.mark.asyncio
async def test_result_posted_message_for_runner_up(client, member, two_checked_in):
    """Confirm the RESULT_POSTED message correctly interpolates a non-WINNER result value"""
    leader_headers, event_id, winner_reg_id, runner_up_reg_id = two_checked_in
    result_payload = {
        "winner_registration_id": runner_up_reg_id,
        "runner_up_registration_id": winner_reg_id,  # member is runner-up
    }
    await client.patch(f"/events/{event_id}/results", headers=leader_headers, json=result_payload)

    response = await client.get(
        "/notifications", headers=member, params={"type": "RESULT_POSTED"}
    )
    body = response.json()
    assert len(body) == 1
    assert body[0]["message"] == "Your result for Line Follower Workshop is now available: RUNNER_UP"


@pytest.mark.asyncio
async def test_unregister_does_not_remove_earlier_registration_notification(client, leader, member):
    """Confirm that cancelling a registration does not delete the earlier REGISTRATION_CONFIRMED notification"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Unregister notification test",
        "description": "An event used to test notification persistence after unregistering",
        "venue": "Lab 204",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/publish", headers=headers)
    await client.post(f"/events/{event_id}/register", headers=member)
    await client.delete(f"/events/{event_id}/register", headers=member)

    response = await client.get(
        "/notifications", headers=member, params={"type": "REGISTRATION_CONFIRMED"}
    )
    assert response.status_code == 200
    assert len(response.json()) == 1

@pytest.mark.asyncio
async def test_list_notifications_filter_is_read_true(client, leader, member, outsider):
    """Verify that is_read=True returns only notifications that have been marked read"""
    leader_headers, group_id = leader
    join = await client.post(f"/groups/{group_id}/join", headers=outsider)
    approve_payload = {"action": "APPROVED"}
    await client.patch(
        f"/groups/{group_id}/requests/{join.json()['id']}", headers=leader_headers, json=approve_payload
    )

    payload = {
        "group_id": group_id,
        "title": "Read filter event",
        "description": "An event used to test the is_read=True filter",
        "venue": "Lab 204",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    create = await client.post("/events", headers=leader_headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/publish", headers=leader_headers)
    await client.post(f"/events/{event_id}/register", headers=member)

    listed = await client.get("/notifications", headers=member, params={"type": "JOIN_APPROVED"})
    join_notification_id = listed.json()[0]["id"]
    await client.patch(f"/notifications/{join_notification_id}/read", headers=member)

    response = await client.get("/notifications", headers=member, params={"is_read": True})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == join_notification_id


@pytest.mark.asyncio
async def test_list_notifications_never_returns_another_members_notifications(client, leader, member, outsider):
    """Verify that a member's notification list never includes another member's notifications"""
    leader_headers, group_id = leader
    join = await client.post(f"/groups/{group_id}/join", headers=outsider)
    approve_payload = {"action": "APPROVED"}
    await client.patch(
        f"/groups/{group_id}/requests/{join.json()['id']}", headers=leader_headers, json=approve_payload
    )

    member_response = await client.get("/notifications", headers=member)
    outsider_response = await client.get("/notifications", headers=outsider)

    member_ids = {item["id"] for item in member_response.json()}
    outsider_ids = {item["id"] for item in outsider_response.json()}
    assert member_ids.isdisjoint(outsider_ids)
    assert len(outsider_ids) >= 1