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
    }
    signup = await client.post("/auth/signup", json=payload)
    return {"Authorization": f"Bearer {signup.json()['access_token']}"}


# ==== raise request ====

@pytest.mark.asyncio
async def test_raise_request_success(client, leader, member):
    """Verify that an approved member can raise an request against their group"""
    _, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GROUP",
        "title": "Cannot access group resources",
        "description": "I am unable to view the shared drive for this group",
    }
    response = await client.post("/requests", headers=member, json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["group_id"] == group_id
    assert body["title"] == "Cannot access group resources"
    assert body["category"] == "GROUP"
    assert body["status"] == "OPEN"
    assert body["message"] == "Request submitted to the group leader"


@pytest.mark.asyncio
async def test_raise_request_with_event_id_success(client, leader, member):
    """Verify that an request can be raised with an associated event_id"""
    headers, group_id = leader
    event_payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    event = await client.post("/events", headers=headers, json=event_payload)
    event_id = event.json()["id"]

    payload = {
        "group_id": group_id,
        "category": "EVENT",
        "title": "Registration is not working",
        "description": "I keep getting an error when trying to register for this event",
        "event_id": event_id,
    }
    response = await client.post("/requests", headers=member, json=payload)
    assert response.status_code == 200
    assert response.json()["category"] == "EVENT"


@pytest.mark.asyncio
async def test_raise_request_by_non_member_succeeds(client, leader, outsider):
    """Confirm that raising an request does not require group membership, since the service has no such check"""
    _, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "General inquiry about the group",
        "description": "I have a question about this group even though I never joined",
    }
    response = await client.post("/requests", headers=outsider, json=payload)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_raise_request_title_min_length_boundary_succeeds(client, leader, member):
    """Validate that raising an request succeeds when the title is exactly at the 3-character minimum"""
    _, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Abc",
        "description": "A title at the minimum length boundary for requests",
    }
    response = await client.post("/requests", headers=member, json=payload)
    assert response.status_code == 200
    assert response.json()["title"] == "Abc"


@pytest.mark.asyncio
async def test_raise_request_title_below_min_length_fails(client, leader, member):
    """Validate that raising an request is rejected when the title is below the 3-character minimum"""
    _, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Ab",
        "description": "A title that is one character too short for requests",
    }
    response = await client.post("/requests", headers=member, json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_raise_request_title_max_length_boundary_succeeds(client, leader, member):
    """Validate that raising an request succeeds when the title is exactly at the 150-character limit"""
    _, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "A" * 150,
        "description": "A title exactly at the maximum length boundary for requests",
    }
    response = await client.post("/requests", headers=member, json=payload)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_raise_request_title_over_max_length_fails(client, leader, member):
    """Validate that raising an request is rejected when the title exceeds the 150-character limit"""
    _, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "A" * 151,
        "description": "A title exceeding the maximum length boundary for requests",
    }
    response = await client.post("/requests", headers=member, json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_raise_request_description_min_length_boundary_succeeds(client, leader, member):
    """Validate that raising an request succeeds when the description is exactly at the 10-character minimum"""
    _, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Short description test",
        "description": "A" * 10,
    }
    response = await client.post("/requests", headers=member, json=payload)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_raise_request_description_below_min_length_fails(client, leader, member):
    """Validate that raising an request is rejected when the description is below the 10-character minimum"""
    _, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Too short description test",
        "description": "A" * 9,
    }
    response = await client.post("/requests", headers=member, json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_raise_request_description_over_max_length_fails(client, leader, member):
    """Validate that raising an request is rejected when the description exceeds the 2000-character limit"""
    _, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Too long description test",
        "description": "A" * 2001,
    }
    response = await client.post("/requests", headers=member, json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_raise_request_invalid_category_fails(client, leader, member):
    """Validate that raising an request is rejected when the category is not a recognized enum value"""
    _, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "BILLING",
        "title": "Invalid category test",
        "description": "This request has a category value that does not exist",
    }
    response = await client.post("/requests", headers=member, json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_raise_request_lowercase_category_fails(client, leader, member):
    """Validate that raising an request is rejected when the category uses lowercase casing"""
    _, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "general",
        "title": "Lowercase category test",
        "description": "This request uses a lowercase category value",
    }
    response = await client.post("/requests", headers=member, json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_raise_request_missing_fields_fails(client, leader, member):
    """Validate that raising an request is rejected when required fields are missing"""
    _, group_id = leader
    payload = {"group_id": group_id}
    response = await client.post("/requests", headers=member, json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_raise_request_unknown_group_fails(client, member):
    """Confirm that raising an request is rejected when the group does not exist"""
    payload = {
        "group_id": 999999,
        "category": "GENERAL",
        "title": "Ghost group request",
        "description": "This group does not exist at all in the system",
    }
    response = await client.post("/requests", headers=member, json=payload)
    assert response.status_code == 404
    assert response.json()["message"] == "Group not found"


@pytest.mark.asyncio
async def test_raise_request_pending_group_fails(client, seed_tenant):
    """Confirm that raising an request is rejected when the group is still PENDING approval"""
    payload = {
        "email": "pendingleader.request@knit.edu.in",
        "full_name": "Pending Leader",
        "password": "Test@1234",
        "confirm_password": "Test@1234",
        "role": "MEMBER",
    }
    signup = await client.post("/auth/signup", json=payload)
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    group_payload = {
        "name": "Pending Request Group",
        "description": "A group left pending for request testing",
        "category": "Technical",
        "type": "OFFICIAL",
    }
    group = await client.post("/groups", headers=headers, json=group_payload)
    group_id = group.json()["id"]

    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Request against a pending group",
        "description": "This group is not active yet so this should fail",
    }
    response = await client.post("/requests", headers=headers, json=payload)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_raise_request_event_from_different_group_fails(client, leader, member):
    """Confirm that raising an request is rejected when event_id belongs to a different group"""
    headers, group_id = leader
    other_group_payload = {
        "name": "Other Group For Request Test",
        "description": "A separate group used to host an unrelated event",
        "category": "Arts",
        "type": "UNOFFICIAL",
    }
    other_group = await client.post("/groups", headers=headers, json=other_group_payload)
    other_group_id = other_group.json()["id"]

    event_payload = {
        "group_id": other_group_id,
        "title": "Unrelated Event",
        "description": "An event that belongs to a different group than the request",
        "venue": "Lab 204",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    event = await client.post("/events", headers=headers, json=event_payload)
    event_id = event.json()["id"]

    payload = {
        "group_id": group_id,
        "category": "EVENT",
        "title": "Wrong group event reference",
        "description": "This event_id belongs to a different group than group_id",
        "event_id": event_id,
    }
    response = await client.post("/requests", headers=member, json=payload)
    assert response.status_code == 404
    assert response.json()["message"] == "Event not found"


@pytest.mark.asyncio
async def test_raise_request_unknown_event_id_fails(client, leader, member):
    """Confirm that raising an request is rejected when event_id does not exist"""
    _, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "EVENT",
        "title": "Ghost event reference",
        "description": "This event_id does not exist anywhere in the system",
        "event_id": 999999,
    }
    response = await client.post("/requests", headers=member, json=payload)
    assert response.status_code == 404
    assert response.json()["message"] == "Event not found"


@pytest.mark.asyncio
async def test_raise_request_without_token_fails(client, leader):
    """Ensure that raising an request is rejected without an access token"""
    _, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Anonymous request attempt",
        "description": "Raised without any authentication token provided",
    }
    response = await client.post("/requests", json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# ==== my requests ====

@pytest.mark.asyncio
async def test_my_requests_returns_own_requests(client, leader, member):
    """Verify that a member can list the requests they have raised"""
    _, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GROUP",
        "title": "My own request",
        "description": "This request was raised by the requesting member",
    }
    raised = await client.post("/requests", headers=member, json=payload)
    request_id = raised.json()["id"]

    response = await client.get("/requests", headers=member)
    assert response.status_code == 200
    body = response.json()
    ids = [item["id"] for item in body]
    assert request_id in ids
    item = next(i for i in body if i["id"] == request_id)
    assert item["group_name"] == "Robotics Group"
    assert item["status"] == "OPEN"
    assert item["response"] is None
    assert item["resolved_at"] is None


@pytest.mark.asyncio
async def test_my_requests_excludes_other_members_requests(client, leader, member, outsider):
    """Confirm that a member's request list never includes another member's requests"""
    _, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Outsider's own request",
        "description": "This request belongs to the outsider, not the member",
    }
    raised = await client.post("/requests", headers=outsider, json=payload)
    request_id = raised.json()["id"]

    response = await client.get("/requests", headers=member)
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert request_id not in ids


@pytest.mark.asyncio
async def test_my_requests_filter_by_status(client, leader, member):
    """Verify that filtering by status returns only matching requests"""
    _, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Status filter request",
        "description": "This request is used to test status filtering",
    }
    raised = await client.post("/requests", headers=member, json=payload)
    request_id = raised.json()["id"]

    open_response = await client.get("/requests", headers=member, params={"status": "OPEN"})
    assert open_response.status_code == 200
    ids = [item["id"] for item in open_response.json()]
    assert request_id in ids

    resolved_response = await client.get("/requests", headers=member, params={"status": "RESOLVED"})
    assert request_id not in [item["id"] for item in resolved_response.json()]


@pytest.mark.asyncio
async def test_my_requests_filter_by_group_id(client, leader, member):
    """Verify that filtering by group_id returns only that group's requests"""
    _, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Group filter request",
        "description": "This request is used to test the group_id filter",
    }
    raised = await client.post("/requests", headers=member, json=payload)
    request_id = raised.json()["id"]

    response = await client.get("/requests", headers=member, params={"group_id": group_id})
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert request_id in ids


@pytest.mark.asyncio
async def test_my_requests_lowercase_status_filter_fails(client, member):
    """Validate that filtering by status is rejected when using lowercase casing"""
    response = await client.get("/requests", headers=member, params={"status": "open"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_my_requests_limit_zero_fails(client, member):
    """Validate that listing requests is rejected when limit is below the minimum of 1"""
    response = await client.get("/requests", headers=member, params={"limit": 0})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_my_requests_limit_over_max_fails(client, member):
    """Validate that listing requests is rejected when limit exceeds the maximum of 100"""
    response = await client.get("/requests", headers=member, params={"limit": 101})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_my_requests_offset_negative_fails(client, member):
    """Validate that listing requests is rejected when offset is negative"""
    response = await client.get("/requests", headers=member, params={"offset": -1})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_my_requests_empty_for_member_with_no_requests(client, outsider):
    """Confirm that a member who has never raised an request gets an empty list"""
    response = await client.get("/requests", headers=outsider)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_my_requests_without_token_fails(client):
    """Ensure that listing personal requests is rejected without an access token"""
    response = await client.get("/requests")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# ==== group queue (leader view) ====

@pytest.mark.asyncio
async def test_group_queue_returns_led_group_requests(client, leader, member):
    """Verify that a leader can view requests raised against groups they lead"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GROUP",
        "title": "Leader queue visibility test",
        "description": "This request should appear in the leader's group queue",
    }
    raised = await client.post("/requests", headers=member, json=payload)
    request_id = raised.json()["id"]

    response = await client.get("/requests/group", headers=headers)
    assert response.status_code == 200
    body = response.json()
    ids = [item["id"] for item in body]
    assert request_id in ids
    item = next(i for i in body if i["id"] == request_id)
    assert item["raised_by"] == "Group Member"
    assert item["group_name"] == "Robotics Group"


@pytest.mark.asyncio
async def test_group_queue_empty_for_non_leader(client, leader, member):
    """Confirm that a plain member with no led groups gets an empty group queue"""
    _, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Not a leader queue test",
        "description": "This member does not lead any group",
    }
    await client.post("/requests", headers=member, json=payload)

    response = await client.get("/requests/group", headers=member)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_group_queue_filter_by_status(client, leader, member):
    """Verify that the group queue can be filtered by status"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Queue status filter test",
        "description": "This request is used to test the leader queue status filter",
    }
    raised = await client.post("/requests", headers=member, json=payload)
    request_id = raised.json()["id"]

    response = await client.get("/requests/group", headers=headers, params={"status": "OPEN"})
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert request_id in ids


@pytest.mark.asyncio
async def test_group_queue_filter_by_group_id(client, leader, member):
    """Verify that the group queue can be filtered by group_id"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Queue group_id filter test",
        "description": "This request is used to test the leader queue group_id filter",
    }
    raised = await client.post("/requests", headers=member, json=payload)
    request_id = raised.json()["id"]

    response = await client.get("/requests/group", headers=headers, params={"group_id": group_id})
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert request_id in ids


@pytest.mark.asyncio
async def test_group_queue_without_token_fails(client):
    """Ensure that requesting the group queue is rejected without an access token"""
    response = await client.get("/requests/group")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# ==== open count ====

@pytest.mark.asyncio
async def test_open_count_reflects_unresolved_requests(client, leader, member):
    """Verify that open-count reflects the number of unresolved requests across led groups"""
    headers, group_id = leader
    before = await client.get("/requests/group/open-count", headers=headers)
    initial_count = before.json()["count"]

    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Open count test request",
        "description": "This request should increase the leader's open count",
    }
    raised = await client.post("/requests", headers=member, json=payload)
    request_id = raised.json()["id"]

    after = await client.get("/requests/group/open-count", headers=headers)
    assert after.json()["count"] == initial_count + 1

    await client.patch(f"/requests/{request_id}/resolve", headers=headers)

    final = await client.get("/requests/group/open-count", headers=headers)
    assert final.json()["count"] == initial_count


@pytest.mark.asyncio
async def test_open_count_counts_in_progress_as_open(client, leader, member):
    """Confirm that an IN_PROGRESS request still counts toward open-count, since only RESOLVED is excluded"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "In progress still open test",
        "description": "This request will be replied to but not resolved",
    }
    raised = await client.post("/requests", headers=member, json=payload)
    request_id = raised.json()["id"]

    before = await client.get("/requests/group/open-count", headers=headers)
    initial_count = before.json()["count"]

    reply_payload = {"reply": "Looking into this now"}
    await client.post(f"/requests/{request_id}/reply", headers=headers, json=reply_payload)

    after = await client.get("/requests/group/open-count", headers=headers)
    assert after.json()["count"] == initial_count


@pytest.mark.asyncio
async def test_open_count_zero_for_non_leader(client, member):
    """Confirm that a member who leads no groups has an open-count of zero"""
    response = await client.get("/requests/group/open-count", headers=member)
    assert response.status_code == 200
    assert response.json()["count"] == 0


# ==== reply ====

@pytest.mark.asyncio
async def test_reply_to_request_success(client, leader, member):
    """Verify that a leader can reply to an request, moving it to IN_PROGRESS"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Reply test request",
        "description": "This request will receive a reply from the leader",
    }
    raised = await client.post("/requests", headers=member, json=payload)
    request_id = raised.json()["id"]

    reply_payload = {"reply": "We are looking into this and will update you soon"}
    response = await client.post(f"/requests/{request_id}/reply", headers=headers, json=reply_payload)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == request_id
    assert body["status"] == "IN_PROGRESS"
    assert body["message"] == "Reply sent to the member"

    listed = await client.get("/requests", headers=member)
    item = next(i for i in listed.json() if i["id"] == request_id)
    assert item["response"]["by"] == "Group Leader"
    assert item["response"]["text"] == "We are looking into this and will update you soon"


@pytest.mark.asyncio
async def test_reply_min_length_boundary_succeeds(client, leader, member):
    """Validate that a reply succeeds when it is exactly at the 2-character minimum"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Short reply boundary test",
        "description": "This request tests the minimum reply length boundary",
    }
    raised = await client.post("/requests", headers=member, json=payload)
    request_id = raised.json()["id"]

    reply_payload = {"reply": "Ok"}
    response = await client.post(f"/requests/{request_id}/reply", headers=headers, json=reply_payload)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_reply_below_min_length_fails(client, leader, member):
    """Validate that a reply is rejected when it is below the 2-character minimum"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Too short reply test",
        "description": "This request tests rejection of too-short replies",
    }
    raised = await client.post("/requests", headers=member, json=payload)
    request_id = raised.json()["id"]

    reply_payload = {"reply": "K"}
    response = await client.post(f"/requests/{request_id}/reply", headers=headers, json=reply_payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_reply_over_max_length_fails(client, leader, member):
    """Validate that a reply is rejected when it exceeds the 2000-character limit"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Too long reply test",
        "description": "This request tests rejection of too-long replies",
    }
    raised = await client.post("/requests", headers=member, json=payload)
    request_id = raised.json()["id"]

    reply_payload = {"reply": "A" * 2001}
    response = await client.post(f"/requests/{request_id}/reply", headers=headers, json=reply_payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_reply_to_resolved_request_fails(client, leader, member):
    """Confirm that replying to an already-resolved request is rejected"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Resolved reply test",
        "description": "This request will be resolved before a reply is attempted",
    }
    raised = await client.post("/requests", headers=member, json=payload)
    request_id = raised.json()["id"]
    await client.patch(f"/requests/{request_id}/resolve", headers=headers)

    reply_payload = {"reply": "Trying to reply after resolution"}
    response = await client.post(f"/requests/{request_id}/reply", headers=headers, json=reply_payload)
    assert response.status_code == 403
    assert response.json()["message"] == "A resolved request cannot be replied to"


@pytest.mark.asyncio
async def test_reply_unknown_request_fails(client, leader):
    """Confirm that replying to a nonexistent request returns not found"""
    headers, _ = leader
    reply_payload = {"reply": "This request does not exist"}
    response = await client.post("/requests/999999/reply", headers=headers, json=reply_payload)
    assert response.status_code == 404
    assert response.json()["message"] == "Request not found"


@pytest.mark.asyncio
async def test_reply_by_non_leader_fails(client, leader, member):
    """Ensure that a plain group member cannot reply to an request"""
    _, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Non leader reply test",
        "description": "A member should not be able to reply to this request",
    }
    raised = await client.post("/requests", headers=member, json=payload)
    request_id = raised.json()["id"]

    reply_payload = {"reply": "Trying to reply as a non-leader"}
    response = await client.post(f"/requests/{request_id}/reply", headers=member, json=reply_payload)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_reply_missing_field_fails(client, leader, member):
    """Validate that replying is rejected when the reply field is missing"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Missing reply field test",
        "description": "This request omits the required reply field",
    }
    raised = await client.post("/requests", headers=member, json=payload)
    request_id = raised.json()["id"]

    response = await client.post(f"/requests/{request_id}/reply", headers=headers, json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_reply_without_token_fails(client, leader, member):
    """Ensure that replying is rejected without an access token"""
    _, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "No token reply test",
        "description": "Trying to reply without any authentication",
    }
    raised = await client.post("/requests", headers=member, json=payload)
    request_id = raised.json()["id"]

    reply_payload = {"reply": "Should not be allowed"}
    response = await client.post(f"/requests/{request_id}/reply", json=reply_payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# ==== resolve ====

@pytest.mark.asyncio
async def test_resolve_request_success(client, leader, member):
    """Verify that a leader can resolve an request"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Resolve test request",
        "description": "This request will be resolved by the leader",
    }
    raised = await client.post("/requests", headers=member, json=payload)
    request_id = raised.json()["id"]

    response = await client.patch(f"/requests/{request_id}/resolve", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == request_id
    assert body["status"] == "RESOLVED"
    assert body["message"] == "Request marked as resolved"

    listed = await client.get("/requests", headers=member)
    item = next(i for i in listed.json() if i["id"] == request_id)
    assert item["resolved_at"] is not None


@pytest.mark.asyncio
async def test_resolve_request_directly_from_open_succeeds(client, leader, member):
    """Confirm that an OPEN request can be resolved directly without going through a reply first"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Direct resolve test",
        "description": "This request skips the reply step and goes straight to resolved",
    }
    raised = await client.post("/requests", headers=member, json=payload)
    request_id = raised.json()["id"]

    response = await client.patch(f"/requests/{request_id}/resolve", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "RESOLVED"


@pytest.mark.asyncio
async def test_resolve_already_resolved_request_fails(client, leader, member):
    """Confirm that resolving an already-resolved request is rejected"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Double resolve test",
        "description": "This request will be resolved more than once",
    }
    raised = await client.post("/requests", headers=member, json=payload)
    request_id = raised.json()["id"]
    await client.patch(f"/requests/{request_id}/resolve", headers=headers)

    response = await client.patch(f"/requests/{request_id}/resolve", headers=headers)
    assert response.status_code == 403
    assert response.json()["message"] == "Request is already resolved"


@pytest.mark.asyncio
async def test_resolve_unknown_request_fails(client, leader):
    """Confirm that resolving a nonexistent request returns not found"""
    headers, _ = leader
    response = await client.patch("/requests/999999/resolve", headers=headers)
    assert response.status_code == 404
    assert response.json()["message"] == "Request not found"


@pytest.mark.asyncio
async def test_resolve_by_non_leader_fails(client, leader, member):
    """Ensure that a plain group member cannot resolve an request"""
    _, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Non leader resolve test",
        "description": "A member should not be able to resolve this request",
    }
    raised = await client.post("/requests", headers=member, json=payload)
    request_id = raised.json()["id"]

    response = await client.patch(f"/requests/{request_id}/resolve", headers=member)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_resolve_cross_tenant_request_fails(client, leader, member):
    """Verify that resolving an request belonging to a group from a different tenant returns not found"""
    other_admin_payload = {
        "email": "admin@otherrequest.edu.in",
        "full_name": "Other Request Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "TENANT_ADMIN",
    }
    other_admin_signup = await client.post("/auth/signup", json=other_admin_payload)
    other_admin_token = other_admin_signup.json()["access_token"]

    tenant_payload = {
        "name": "Other Request Tenant",
        "email_suffix": "otherrequest.edu.in",
        "description": "A separate tenant for request scoping tests",
    }
    await client.post(
        "/tenant/onboarding", json=tenant_payload,
        headers={"Authorization": f"Bearer {other_admin_token}"},
    )

    other_member_payload = {
        "email": "leader@otherrequest.edu.in",
        "full_name": "Other Request Leader",
        "password": "Leader@123",
        "confirm_password": "Leader@123",
        "role": "MEMBER",
    }
    other_member_signup = await client.post("/auth/signup", json=other_member_payload)
    other_headers = {"Authorization": f"Bearer {other_member_signup.json()['access_token']}"}

    group_payload = {
        "name": "Foreign Request Group",
        "description": "A group that belongs to a different tenant",
        "category": "Technical",
        "type": "UNOFFICIAL",
    }
    other_group = await client.post("/groups", headers=other_headers, json=group_payload)
    other_group_id = other_group.json()["id"]

    request_payload = {
        "group_id": other_group_id,
        "category": "GENERAL",
        "title": "Foreign tenant request",
        "description": "This request belongs to a group in a different tenant",
    }
    raised = await client.post("/requests", headers=other_headers, json=request_payload)
    request_id = raised.json()["id"]

    headers, _ = leader
    response = await client.patch(f"/requests/{request_id}/resolve", headers=headers)
    assert response.status_code == 404
    assert response.json()["message"] == "Request not found"


@pytest.mark.asyncio
async def test_resolve_without_token_fails(client, leader, member):
    """Ensure that resolving is rejected without an access token"""
    _, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "No token resolve test",
        "description": "Trying to resolve without any authentication",
    }
    raised = await client.post("/requests", headers=member, json=payload)
    request_id = raised.json()["id"]

    response = await client.patch(f"/requests/{request_id}/resolve")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.asyncio
async def test_reply_cross_tenant_request_fails(client, leader):
    """Verify that replying to an request belonging to a group from a different tenant returns not found"""
    other_admin_payload = {
        "email": "admin@otherrequestreply.edu.in",
        "full_name": "Other Request Reply Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "TENANT_ADMIN",
    }
    other_admin_signup = await client.post("/auth/signup", json=other_admin_payload)
    other_admin_token = other_admin_signup.json()["access_token"]

    tenant_payload = {
        "name": "Other Request Reply Tenant",
        "email_suffix": "otherrequestreply.edu.in",
        "description": "A separate tenant for request reply scoping tests",
    }
    await client.post(
        "/tenant/onboarding", json=tenant_payload,
        headers={"Authorization": f"Bearer {other_admin_token}"},
    )

    other_member_payload = {
        "email": "leader@otherrequestreply.edu.in",
        "full_name": "Other Request Reply Leader",
        "password": "Leader@123",
        "confirm_password": "Leader@123",
        "role": "MEMBER",
    }
    other_member_signup = await client.post("/auth/signup", json=other_member_payload)
    other_headers = {"Authorization": f"Bearer {other_member_signup.json()['access_token']}"}

    group_payload = {
        "name": "Foreign Reply Group",
        "description": "A group that belongs to a different tenant",
        "category": "Technical",
        "type": "UNOFFICIAL",
    }
    other_group = await client.post("/groups", headers=other_headers, json=group_payload)
    other_group_id = other_group.json()["id"]

    request_payload = {
        "group_id": other_group_id,
        "category": "GENERAL",
        "title": "Foreign tenant reply target",
        "description": "This request belongs to a group in a different tenant",
    }
    raised = await client.post("/requests", headers=other_headers, json=request_payload)
    request_id = raised.json()["id"]

    headers, _ = leader
    reply_payload = {"reply": "Trying to reply across tenants"}
    response = await client.post(f"/requests/{request_id}/reply", headers=headers, json=reply_payload)
    assert response.status_code == 404
    assert response.json()["message"] == "Request not found"


@pytest.mark.asyncio
async def test_reply_twice_updates_response_to_latest(client, leader, member):
    """Confirm that a second reply overwrites the response with the latest text, since only RESOLVED blocks replying"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Double reply test",
        "description": "This request will receive two replies in a row",
    }
    raised = await client.post("/requests", headers=member, json=payload)
    request_id = raised.json()["id"]

    first_reply = {"reply": "First response to this request"}
    first = await client.post(f"/requests/{request_id}/reply", headers=headers, json=first_reply)
    assert first.status_code == 200
    assert first.json()["status"] == "IN_PROGRESS"

    second_reply = {"reply": "Updated, corrected response"}
    second = await client.post(f"/requests/{request_id}/reply", headers=headers, json=second_reply)
    assert second.status_code == 200
    assert second.json()["status"] == "IN_PROGRESS"

    listed = await client.get("/requests", headers=member)
    item = next(i for i in listed.json() if i["id"] == request_id)
    assert item["response"]["text"] == "Updated, corrected response"


@pytest.mark.asyncio
async def test_reply_then_resolve_succeeds(client, leader, member):
    """Verify that an request can move from IN_PROGRESS to RESOLVED after being replied to"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Reply then resolve test",
        "description": "This request is replied to first, then resolved",
    }
    raised = await client.post("/requests", headers=member, json=payload)
    request_id = raised.json()["id"]

    reply_payload = {"reply": "We are on it"}
    await client.post(f"/requests/{request_id}/reply", headers=headers, json=reply_payload)

    response = await client.patch(f"/requests/{request_id}/resolve", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "RESOLVED"


@pytest.mark.asyncio
async def test_group_queue_group_id_for_unled_group_returns_empty(client, leader, member):
    """Confirm that filtering the group queue by a group_id the caller doesn't lead returns an empty list, not another leader's requests"""
    headers, group_id = leader
    other_leader_payload = {
        "email": "othergroupqueueleader@knit.edu.in",
        "full_name": "Other Queue Leader",
        "password": "Test@1234",
        "confirm_password": "Test@1234",
        "role": "MEMBER",
    }
    signup = await client.post("/auth/signup", json=other_leader_payload)
    other_headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    other_group_payload = {
        "name": "Unled Queue Group",
        "description": "A group the requesting leader does not lead",
        "category": "Technical",
        "type": "UNOFFICIAL",
    }
    other_group = await client.post("/groups", headers=other_headers, json=other_group_payload)
    other_group_id = other_group.json()["id"]

    request_payload = {
        "group_id": other_group_id,
        "category": "GENERAL",
        "title": "Request in a group the caller does not lead",
        "description": "This should never appear in the original leader's filtered queue",
    }
    await client.post("/requests", headers=other_headers, json=request_payload)

    response = await client.get("/requests/group", headers=headers, params={"group_id": other_group_id})
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_open_count_aggregates_across_multiple_led_groups(client, leader, member):
    """Verify that open-count sums unresolved requests across every group the member leads, not just one"""
    headers, first_group_id = leader
    second_group_payload = {
        "name": "Second Led Group",
        "description": "A second group led by the same member",
        "category": "Arts",
        "type": "UNOFFICIAL",
    }
    second_group = await client.post("/groups", headers=headers, json=second_group_payload)
    second_group_id = second_group.json()["id"]

    before = await client.get("/requests/group/open-count", headers=headers)
    initial_count = before.json()["count"]

    first_payload = {
        "group_id": first_group_id,
        "category": "GENERAL",
        "title": "Request in first led group",
        "description": "An unresolved request in the first group the member leads",
    }
    await client.post("/requests", headers=member, json=first_payload)

    second_payload = {
        "group_id": second_group_id,
        "category": "GENERAL",
        "title": "Request in second led group",
        "description": "An unresolved request in the second group the member leads",
    }
    await client.post("/requests", headers=member, json=second_payload)

    after = await client.get("/requests/group/open-count", headers=headers)
    assert after.json()["count"] == initial_count + 2


@pytest.mark.asyncio
async def test_my_requests_event_id_is_none_when_not_provided(client, leader, member):
    """Confirm that event_id is null in the response when the request was raised without one"""
    _, group_id = leader
    payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "No event reference request",
        "description": "This request was raised without an associated event",
    }
    raised = await client.post("/requests", headers=member, json=payload)
    request_id = raised.json()["id"]

    listed = await client.get("/requests", headers=member)
    item = next(i for i in listed.json() if i["id"] == request_id)
    assert item["event_id"] is None


@pytest.mark.asyncio
async def test_my_requests_limit_caps_returned_items(client, leader, member):
    """Confirm that limit actually caps the number of requests returned, not just accepted"""
    _, group_id = leader
    for i in range(3):
        payload = {
            "group_id": group_id,
            "category": "GENERAL",
            "title": f"Pagination request {i}",
            "description": f"Request number {i} used to test the limit cap",
        }
        await client.post("/requests", headers=member, json=payload)

    response = await client.get("/requests", headers=member, params={"limit": 1})
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_raise_request_against_draft_event_succeeds(client, leader, member):
    """Confirm that an request can be raised against a draft, unpublished event since no status check exists"""
    headers, group_id = leader
    event_payload = {
        "group_id": group_id,
        "title": "Unpublished Workshop",
        "description": "An event that has never been published",
        "venue": "Lab 204",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    event = await client.post("/events", headers=headers, json=event_payload)
    event_id = event.json()["id"]

    payload = {
        "group_id": group_id,
        "category": "EVENT",
        "title": "Request against draft event",
        "description": "This event has never been published but the request should still be accepted",
        "event_id": event_id,
    }
    response = await client.post("/requests", headers=member, json=payload)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_raise_request_against_past_event_succeeds(client, db_session, leader, member):
    """Confirm that an request can be raised against an event whose window has already ended"""
    from datetime import datetime, timedelta, timezone
    from app.models import Event

    headers, group_id = leader
    event_payload = {
        "group_id": group_id,
        "title": "Concluded Workshop",
        "description": "An event that will be moved into the past",
        "venue": "Lab 204",
        "starts_at": future_time(2),
        "ends_at": future_time(4),
    }
    event = await client.post("/events", headers=headers, json=event_payload)
    event_id = event.json()["id"]
    await client.patch(f"/events/{event_id}/publish", headers=headers)

    stored_event = await db_session.get(Event, event_id)
    stored_event.starts_at = datetime.now(timezone.utc) - timedelta(hours=5)
    stored_event.ends_at = datetime.now(timezone.utc) - timedelta(hours=3)
    await db_session.flush()

    payload = {
        "group_id": group_id,
        "category": "EVENT",
        "title": "Request against concluded event",
        "description": "This event has already ended but the request should still be accepted",
        "event_id": event_id,
    }
    response = await client.post("/requests", headers=member, json=payload)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_raise_request_by_non_registrant_succeeds(client, leader, member):
    """Confirm that a member can raise an request against an event they never registered for"""
    headers, group_id = leader
    event_payload = {
        "group_id": group_id,
        "title": "Never Registered Workshop",
        "description": "An event the request-raiser never signs up for",
        "venue": "Lab 204",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    event = await client.post("/events", headers=headers, json=event_payload)
    event_id = event.json()["id"]
    await client.patch(f"/events/{event_id}/publish", headers=headers)

    payload = {
        "group_id": group_id,
        "category": "EVENT",
        "title": "Request without registering first",
        "description": "This member never registered for the event but still has a question about it",
        "event_id": event_id,
    }
    response = await client.post("/requests", headers=member, json=payload)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_group_queue_open_sorts_before_in_progress(client, leader, member):
    """Confirm that OPEN requests sort before IN_PROGRESS ones in the leader queue, since status is a native Postgres enum ordered by declaration position, not alphabetically"""
    headers, group_id = leader
    open_payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Still open request",
        "description": "This request remains untouched in the OPEN status",
    }
    open_request = await client.post("/requests", headers=member, json=open_payload)
    open_id = open_request.json()["id"]

    in_progress_payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "In progress request",
        "description": "This request will be replied to, moving it to IN_PROGRESS",
    }
    in_progress_request = await client.post("/requests", headers=member, json=in_progress_payload)
    in_progress_id = in_progress_request.json()["id"]
    reply_payload = {"reply": "Working on this one"}
    await client.post(f"/requests/{in_progress_id}/reply", headers=headers, json=reply_payload)

    response = await client.get("/requests/group", headers=headers)
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]

    assert ids.index(open_id) < ids.index(in_progress_id)

@pytest.mark.asyncio
async def test_group_queue_full_status_order_open_in_progress_resolved(client, leader, member):
    """Confirm the full native-enum ordering: OPEN, then IN_PROGRESS, then RESOLVED"""
    headers, group_id = leader

    resolved_payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Will be resolved",
        "description": "This request will be resolved directly",
    }
    resolved_request = await client.post("/requests", headers=member, json=resolved_payload)
    resolved_id = resolved_request.json()["id"]
    await client.patch(f"/requests/{resolved_id}/resolve", headers=headers)

    in_progress_payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Will be in progress",
        "description": "This request will be replied to but not resolved",
    }
    in_progress_request = await client.post("/requests", headers=member, json=in_progress_payload)
    in_progress_id = in_progress_request.json()["id"]
    await client.post(f"/requests/{in_progress_id}/reply", headers=headers, json={"reply": "On it"})

    open_payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Stays open",
        "description": "This request is left untouched in the OPEN status",
    }
    open_request = await client.post("/requests", headers=member, json=open_payload)
    open_id = open_request.json()["id"]

    response = await client.get("/requests/group", headers=headers)
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert ids.index(open_id) < ids.index(in_progress_id) < ids.index(resolved_id)

@pytest.mark.asyncio
async def test_group_queue_same_status_sorts_oldest_first(client, db_session, leader, member):
    """Confirm that within the same status, the group queue orders oldest-first, unlike other feeds in the app which sort newest-first"""
    from datetime import datetime, timedelta
    from app.models import Request

    headers, group_id = leader
    first_payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Raised first",
        "description": "This request is raised before the second one",
    }
    first_request = await client.post("/requests", headers=member, json=first_payload)
    first_id = first_request.json()["id"]

    second_payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "Raised second",
        "description": "This request is raised after the first one",
    }
    second_request = await client.post("/requests", headers=member, json=second_payload)
    second_id = second_request.json()["id"]

    # force distinct timestamps — same-transaction func.now() can otherwise tie
    request_row = await db_session.get(Request, second_id)
    request_row.created_at = datetime.now() + timedelta(seconds=5)
    await db_session.flush()

    response = await client.get("/requests/group", headers=headers)
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert ids.index(first_id) < ids.index(second_id)

@pytest.mark.asyncio
async def test_my_requests_sorts_newest_first(client, db_session, leader, member):
    """Confirm that a member's own request list sorts newest-first, in contrast to the leader queue's oldest-first ordering"""
    from datetime import datetime, timedelta
    from app.models import Request

    _, group_id = leader
    first_payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "My first request",
        "description": "Raised before the second request",
    }
    first_request = await client.post("/requests", headers=member, json=first_payload)
    first_id = first_request.json()["id"]

    second_payload = {
        "group_id": group_id,
        "category": "GENERAL",
        "title": "My second request",
        "description": "Raised after the first request",
    }
    second_request = await client.post("/requests", headers=member, json=second_payload)
    second_id = second_request.json()["id"]

    request_row = await db_session.get(Request, second_id)
    request_row.created_at = datetime.now() + timedelta(seconds=5)
    await db_session.flush()

    response = await client.get("/requests", headers=member)
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert ids.index(second_id) < ids.index(first_id)