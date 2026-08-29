import pytest
from datetime import datetime, timedelta, timezone


def future_time(hours: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


# ==== fixtures ====

@pytest.fixture
async def leader(client, seed_college):
    """A student who owns an active club. Yields (headers, club_id)."""
    payload = {
        "email": "leader@knit.edu.in",
        "full_name": "Club Leader",
        "password": "Test@1234",
        "confirm_password": "Test@1234",
        "role": "STUDENT",
    }
    signup = await client.post("/auth/signup", json=payload)
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    payload = {
        "name": "Robotics Club",
        "description": "A club for building robots and breaking budgets",
        "category": "Technical",
        "type": "UNOFFICIAL",
    }
    club = await client.post("/clubs", headers=headers, json=payload)
    return headers, club.json()["id"]


@pytest.fixture
async def member(client, seed_college, leader):
    """An approved member of the leader's club."""
    leader_headers, club_id = leader
    payload = {
        "email": "member@knit.edu.in",
        "full_name": "Club Member",
        "password": "Test@1234",
        "confirm_password": "Test@1234",
        "role": "STUDENT",
    }
    signup = await client.post("/auth/signup", json=payload)
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    join = await client.post(f"/clubs/{club_id}/join", headers=headers)
    payload = {"action": "APPROVED"}
    await client.patch(
        f"/clubs/{club_id}/requests/{join.json()['id']}",
        headers=leader_headers,
        json=payload,
    )
    return headers


@pytest.fixture
async def outsider(client, seed_college):
    """A student of the same college who belongs to no club."""
    payload = {
        "email": "outsider@knit.edu.in",
        "full_name": "Outsider Student",
        "password": "Test@1234",
        "confirm_password": "Test@1234",
        "role": "STUDENT",
    }
    signup = await client.post("/auth/signup", json=payload)
    return {"Authorization": f"Bearer {signup.json()['access_token']}"}


# ==== raise issue ====

@pytest.mark.asyncio
async def test_raise_issue_success(client, leader, member):
    """Verify that an approved member can raise an issue against their club"""
    _, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "CLUB",
        "title": "Cannot access club resources",
        "description": "I am unable to view the shared drive for this club",
    }
    response = await client.post("/issues", headers=member, json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["club_id"] == club_id
    assert body["title"] == "Cannot access club resources"
    assert body["category"] == "CLUB"
    assert body["status"] == "OPEN"
    assert body["message"] == "Issue submitted to the club leader"


@pytest.mark.asyncio
async def test_raise_issue_with_event_id_success(client, leader, member):
    """Verify that an issue can be raised with an associated event_id"""
    headers, club_id = leader
    event_payload = {
        "club_id": club_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    event = await client.post("/events", headers=headers, json=event_payload)
    event_id = event.json()["id"]

    payload = {
        "club_id": club_id,
        "category": "EVENT",
        "title": "Registration is not working",
        "description": "I keep getting an error when trying to register for this event",
        "event_id": event_id,
    }
    response = await client.post("/issues", headers=member, json=payload)
    assert response.status_code == 200
    assert response.json()["category"] == "EVENT"


@pytest.mark.asyncio
async def test_raise_issue_by_non_member_succeeds(client, leader, outsider):
    """Confirm that raising an issue does not require club membership, since the service has no such check"""
    _, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "General inquiry about the club",
        "description": "I have a question about this club even though I never joined",
    }
    response = await client.post("/issues", headers=outsider, json=payload)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_raise_issue_title_min_length_boundary_succeeds(client, leader, member):
    """Validate that raising an issue succeeds when the title is exactly at the 3-character minimum"""
    _, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Abc",
        "description": "A title at the minimum length boundary for issues",
    }
    response = await client.post("/issues", headers=member, json=payload)
    assert response.status_code == 200
    assert response.json()["title"] == "Abc"


@pytest.mark.asyncio
async def test_raise_issue_title_below_min_length_fails(client, leader, member):
    """Validate that raising an issue is rejected when the title is below the 3-character minimum"""
    _, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Ab",
        "description": "A title that is one character too short for issues",
    }
    response = await client.post("/issues", headers=member, json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_raise_issue_title_max_length_boundary_succeeds(client, leader, member):
    """Validate that raising an issue succeeds when the title is exactly at the 150-character limit"""
    _, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "A" * 150,
        "description": "A title exactly at the maximum length boundary for issues",
    }
    response = await client.post("/issues", headers=member, json=payload)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_raise_issue_title_over_max_length_fails(client, leader, member):
    """Validate that raising an issue is rejected when the title exceeds the 150-character limit"""
    _, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "A" * 151,
        "description": "A title exceeding the maximum length boundary for issues",
    }
    response = await client.post("/issues", headers=member, json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_raise_issue_description_min_length_boundary_succeeds(client, leader, member):
    """Validate that raising an issue succeeds when the description is exactly at the 10-character minimum"""
    _, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Short description test",
        "description": "A" * 10,
    }
    response = await client.post("/issues", headers=member, json=payload)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_raise_issue_description_below_min_length_fails(client, leader, member):
    """Validate that raising an issue is rejected when the description is below the 10-character minimum"""
    _, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Too short description test",
        "description": "A" * 9,
    }
    response = await client.post("/issues", headers=member, json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_raise_issue_description_over_max_length_fails(client, leader, member):
    """Validate that raising an issue is rejected when the description exceeds the 2000-character limit"""
    _, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Too long description test",
        "description": "A" * 2001,
    }
    response = await client.post("/issues", headers=member, json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_raise_issue_invalid_category_fails(client, leader, member):
    """Validate that raising an issue is rejected when the category is not a recognized enum value"""
    _, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "BILLING",
        "title": "Invalid category test",
        "description": "This issue has a category value that does not exist",
    }
    response = await client.post("/issues", headers=member, json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_raise_issue_lowercase_category_fails(client, leader, member):
    """Validate that raising an issue is rejected when the category uses lowercase casing"""
    _, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "general",
        "title": "Lowercase category test",
        "description": "This issue uses a lowercase category value",
    }
    response = await client.post("/issues", headers=member, json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_raise_issue_missing_fields_fails(client, leader, member):
    """Validate that raising an issue is rejected when required fields are missing"""
    _, club_id = leader
    payload = {"club_id": club_id}
    response = await client.post("/issues", headers=member, json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_raise_issue_unknown_club_fails(client, member):
    """Confirm that raising an issue is rejected when the club does not exist"""
    payload = {
        "club_id": 999999,
        "category": "GENERAL",
        "title": "Ghost club issue",
        "description": "This club does not exist at all in the system",
    }
    response = await client.post("/issues", headers=member, json=payload)
    assert response.status_code == 404
    assert response.json()["message"] == "Club not found"


@pytest.mark.asyncio
async def test_raise_issue_pending_club_fails(client, seed_college):
    """Confirm that raising an issue is rejected when the club is still PENDING approval"""
    payload = {
        "email": "pendingleader.issue@knit.edu.in",
        "full_name": "Pending Leader",
        "password": "Test@1234",
        "confirm_password": "Test@1234",
        "role": "STUDENT",
    }
    signup = await client.post("/auth/signup", json=payload)
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    club_payload = {
        "name": "Pending Issue Club",
        "description": "A club left pending for issue testing",
        "category": "Technical",
        "type": "OFFICIAL",
    }
    club = await client.post("/clubs", headers=headers, json=club_payload)
    club_id = club.json()["id"]

    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Issue against a pending club",
        "description": "This club is not active yet so this should fail",
    }
    response = await client.post("/issues", headers=headers, json=payload)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_raise_issue_event_from_different_club_fails(client, leader, member):
    """Confirm that raising an issue is rejected when event_id belongs to a different club"""
    headers, club_id = leader
    other_club_payload = {
        "name": "Other Club For Issue Test",
        "description": "A separate club used to host an unrelated event",
        "category": "Arts",
        "type": "UNOFFICIAL",
    }
    other_club = await client.post("/clubs", headers=headers, json=other_club_payload)
    other_club_id = other_club.json()["id"]

    event_payload = {
        "club_id": other_club_id,
        "title": "Unrelated Event",
        "description": "An event that belongs to a different club than the issue",
        "venue": "Lab 204",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    event = await client.post("/events", headers=headers, json=event_payload)
    event_id = event.json()["id"]

    payload = {
        "club_id": club_id,
        "category": "EVENT",
        "title": "Wrong club event reference",
        "description": "This event_id belongs to a different club than club_id",
        "event_id": event_id,
    }
    response = await client.post("/issues", headers=member, json=payload)
    assert response.status_code == 404
    assert response.json()["message"] == "Event not found"


@pytest.mark.asyncio
async def test_raise_issue_unknown_event_id_fails(client, leader, member):
    """Confirm that raising an issue is rejected when event_id does not exist"""
    _, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "EVENT",
        "title": "Ghost event reference",
        "description": "This event_id does not exist anywhere in the system",
        "event_id": 999999,
    }
    response = await client.post("/issues", headers=member, json=payload)
    assert response.status_code == 404
    assert response.json()["message"] == "Event not found"


@pytest.mark.asyncio
async def test_raise_issue_without_token_fails(client, leader):
    """Ensure that raising an issue is rejected without an access token"""
    _, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Anonymous issue attempt",
        "description": "Raised without any authentication token provided",
    }
    response = await client.post("/issues", json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# ==== my issues ====

@pytest.mark.asyncio
async def test_my_issues_returns_own_issues(client, leader, member):
    """Verify that a student can list the issues they have raised"""
    _, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "CLUB",
        "title": "My own issue",
        "description": "This issue was raised by the requesting student",
    }
    raised = await client.post("/issues", headers=member, json=payload)
    issue_id = raised.json()["id"]

    response = await client.get("/issues", headers=member)
    assert response.status_code == 200
    body = response.json()
    ids = [item["id"] for item in body]
    assert issue_id in ids
    item = next(i for i in body if i["id"] == issue_id)
    assert item["club_name"] == "Robotics Club"
    assert item["status"] == "OPEN"
    assert item["response"] is None
    assert item["resolved_at"] is None


@pytest.mark.asyncio
async def test_my_issues_excludes_other_students_issues(client, leader, member, outsider):
    """Confirm that a student's issue list never includes another student's issues"""
    _, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Outsider's own issue",
        "description": "This issue belongs to the outsider, not the member",
    }
    raised = await client.post("/issues", headers=outsider, json=payload)
    issue_id = raised.json()["id"]

    response = await client.get("/issues", headers=member)
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert issue_id not in ids


@pytest.mark.asyncio
async def test_my_issues_filter_by_status(client, leader, member):
    """Verify that filtering by status returns only matching issues"""
    _, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Status filter issue",
        "description": "This issue is used to test status filtering",
    }
    raised = await client.post("/issues", headers=member, json=payload)
    issue_id = raised.json()["id"]

    open_response = await client.get("/issues", headers=member, params={"status": "OPEN"})
    assert open_response.status_code == 200
    ids = [item["id"] for item in open_response.json()]
    assert issue_id in ids

    resolved_response = await client.get("/issues", headers=member, params={"status": "RESOLVED"})
    assert issue_id not in [item["id"] for item in resolved_response.json()]


@pytest.mark.asyncio
async def test_my_issues_filter_by_club_id(client, leader, member):
    """Verify that filtering by club_id returns only that club's issues"""
    _, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Club filter issue",
        "description": "This issue is used to test the club_id filter",
    }
    raised = await client.post("/issues", headers=member, json=payload)
    issue_id = raised.json()["id"]

    response = await client.get("/issues", headers=member, params={"club_id": club_id})
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert issue_id in ids


@pytest.mark.asyncio
async def test_my_issues_lowercase_status_filter_fails(client, member):
    """Validate that filtering by status is rejected when using lowercase casing"""
    response = await client.get("/issues", headers=member, params={"status": "open"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_my_issues_limit_zero_fails(client, member):
    """Validate that listing issues is rejected when limit is below the minimum of 1"""
    response = await client.get("/issues", headers=member, params={"limit": 0})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_my_issues_limit_over_max_fails(client, member):
    """Validate that listing issues is rejected when limit exceeds the maximum of 100"""
    response = await client.get("/issues", headers=member, params={"limit": 101})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_my_issues_offset_negative_fails(client, member):
    """Validate that listing issues is rejected when offset is negative"""
    response = await client.get("/issues", headers=member, params={"offset": -1})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_my_issues_empty_for_student_with_no_issues(client, outsider):
    """Confirm that a student who has never raised an issue gets an empty list"""
    response = await client.get("/issues", headers=outsider)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_my_issues_without_token_fails(client):
    """Ensure that listing personal issues is rejected without an access token"""
    response = await client.get("/issues")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# ==== club queue (leader view) ====

@pytest.mark.asyncio
async def test_club_queue_returns_led_club_issues(client, leader, member):
    """Verify that a leader can view issues raised against clubs they lead"""
    headers, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "CLUB",
        "title": "Leader queue visibility test",
        "description": "This issue should appear in the leader's club queue",
    }
    raised = await client.post("/issues", headers=member, json=payload)
    issue_id = raised.json()["id"]

    response = await client.get("/issues/club", headers=headers)
    assert response.status_code == 200
    body = response.json()
    ids = [item["id"] for item in body]
    assert issue_id in ids
    item = next(i for i in body if i["id"] == issue_id)
    assert item["raised_by"] == "Club Member"
    assert item["club_name"] == "Robotics Club"


@pytest.mark.asyncio
async def test_club_queue_empty_for_non_leader(client, leader, member):
    """Confirm that a plain member with no led clubs gets an empty club queue"""
    _, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Not a leader queue test",
        "description": "This member does not lead any club",
    }
    await client.post("/issues", headers=member, json=payload)

    response = await client.get("/issues/club", headers=member)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_club_queue_filter_by_status(client, leader, member):
    """Verify that the club queue can be filtered by status"""
    headers, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Queue status filter test",
        "description": "This issue is used to test the leader queue status filter",
    }
    raised = await client.post("/issues", headers=member, json=payload)
    issue_id = raised.json()["id"]

    response = await client.get("/issues/club", headers=headers, params={"status": "OPEN"})
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert issue_id in ids


@pytest.mark.asyncio
async def test_club_queue_filter_by_club_id(client, leader, member):
    """Verify that the club queue can be filtered by club_id"""
    headers, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Queue club_id filter test",
        "description": "This issue is used to test the leader queue club_id filter",
    }
    raised = await client.post("/issues", headers=member, json=payload)
    issue_id = raised.json()["id"]

    response = await client.get("/issues/club", headers=headers, params={"club_id": club_id})
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert issue_id in ids


@pytest.mark.asyncio
async def test_club_queue_without_token_fails(client):
    """Ensure that requesting the club queue is rejected without an access token"""
    response = await client.get("/issues/club")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# ==== open count ====

@pytest.mark.asyncio
async def test_open_count_reflects_unresolved_issues(client, leader, member):
    """Verify that open-count reflects the number of unresolved issues across led clubs"""
    headers, club_id = leader
    before = await client.get("/issues/club/open-count", headers=headers)
    initial_count = before.json()["count"]

    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Open count test issue",
        "description": "This issue should increase the leader's open count",
    }
    raised = await client.post("/issues", headers=member, json=payload)
    issue_id = raised.json()["id"]

    after = await client.get("/issues/club/open-count", headers=headers)
    assert after.json()["count"] == initial_count + 1

    await client.patch(f"/issues/{issue_id}/resolve", headers=headers)

    final = await client.get("/issues/club/open-count", headers=headers)
    assert final.json()["count"] == initial_count


@pytest.mark.asyncio
async def test_open_count_counts_in_progress_as_open(client, leader, member):
    """Confirm that an IN_PROGRESS issue still counts toward open-count, since only RESOLVED is excluded"""
    headers, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "In progress still open test",
        "description": "This issue will be replied to but not resolved",
    }
    raised = await client.post("/issues", headers=member, json=payload)
    issue_id = raised.json()["id"]

    before = await client.get("/issues/club/open-count", headers=headers)
    initial_count = before.json()["count"]

    reply_payload = {"reply": "Looking into this now"}
    await client.post(f"/issues/{issue_id}/reply", headers=headers, json=reply_payload)

    after = await client.get("/issues/club/open-count", headers=headers)
    assert after.json()["count"] == initial_count


@pytest.mark.asyncio
async def test_open_count_zero_for_non_leader(client, member):
    """Confirm that a student who leads no clubs has an open-count of zero"""
    response = await client.get("/issues/club/open-count", headers=member)
    assert response.status_code == 200
    assert response.json()["count"] == 0


# ==== reply ====

@pytest.mark.asyncio
async def test_reply_to_issue_success(client, leader, member):
    """Verify that a leader can reply to an issue, moving it to IN_PROGRESS"""
    headers, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Reply test issue",
        "description": "This issue will receive a reply from the leader",
    }
    raised = await client.post("/issues", headers=member, json=payload)
    issue_id = raised.json()["id"]

    reply_payload = {"reply": "We are looking into this and will update you soon"}
    response = await client.post(f"/issues/{issue_id}/reply", headers=headers, json=reply_payload)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == issue_id
    assert body["status"] == "IN_PROGRESS"
    assert body["message"] == "Reply sent to the student"

    listed = await client.get("/issues", headers=member)
    item = next(i for i in listed.json() if i["id"] == issue_id)
    assert item["response"]["by"] == "Club Leader"
    assert item["response"]["text"] == "We are looking into this and will update you soon"


@pytest.mark.asyncio
async def test_reply_min_length_boundary_succeeds(client, leader, member):
    """Validate that a reply succeeds when it is exactly at the 2-character minimum"""
    headers, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Short reply boundary test",
        "description": "This issue tests the minimum reply length boundary",
    }
    raised = await client.post("/issues", headers=member, json=payload)
    issue_id = raised.json()["id"]

    reply_payload = {"reply": "Ok"}
    response = await client.post(f"/issues/{issue_id}/reply", headers=headers, json=reply_payload)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_reply_below_min_length_fails(client, leader, member):
    """Validate that a reply is rejected when it is below the 2-character minimum"""
    headers, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Too short reply test",
        "description": "This issue tests rejection of too-short replies",
    }
    raised = await client.post("/issues", headers=member, json=payload)
    issue_id = raised.json()["id"]

    reply_payload = {"reply": "K"}
    response = await client.post(f"/issues/{issue_id}/reply", headers=headers, json=reply_payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_reply_over_max_length_fails(client, leader, member):
    """Validate that a reply is rejected when it exceeds the 2000-character limit"""
    headers, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Too long reply test",
        "description": "This issue tests rejection of too-long replies",
    }
    raised = await client.post("/issues", headers=member, json=payload)
    issue_id = raised.json()["id"]

    reply_payload = {"reply": "A" * 2001}
    response = await client.post(f"/issues/{issue_id}/reply", headers=headers, json=reply_payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_reply_to_resolved_issue_fails(client, leader, member):
    """Confirm that replying to an already-resolved issue is rejected"""
    headers, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Resolved reply test",
        "description": "This issue will be resolved before a reply is attempted",
    }
    raised = await client.post("/issues", headers=member, json=payload)
    issue_id = raised.json()["id"]
    await client.patch(f"/issues/{issue_id}/resolve", headers=headers)

    reply_payload = {"reply": "Trying to reply after resolution"}
    response = await client.post(f"/issues/{issue_id}/reply", headers=headers, json=reply_payload)
    assert response.status_code == 403
    assert response.json()["message"] == "A resolved issue cannot be replied to"


@pytest.mark.asyncio
async def test_reply_unknown_issue_fails(client, leader):
    """Confirm that replying to a nonexistent issue returns not found"""
    headers, _ = leader
    reply_payload = {"reply": "This issue does not exist"}
    response = await client.post("/issues/999999/reply", headers=headers, json=reply_payload)
    assert response.status_code == 404
    assert response.json()["message"] == "Issue not found"


@pytest.mark.asyncio
async def test_reply_by_non_leader_fails(client, leader, member):
    """Ensure that a plain club member cannot reply to an issue"""
    _, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Non leader reply test",
        "description": "A member should not be able to reply to this issue",
    }
    raised = await client.post("/issues", headers=member, json=payload)
    issue_id = raised.json()["id"]

    reply_payload = {"reply": "Trying to reply as a non-leader"}
    response = await client.post(f"/issues/{issue_id}/reply", headers=member, json=reply_payload)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_reply_missing_field_fails(client, leader, member):
    """Validate that replying is rejected when the reply field is missing"""
    headers, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Missing reply field test",
        "description": "This request omits the required reply field",
    }
    raised = await client.post("/issues", headers=member, json=payload)
    issue_id = raised.json()["id"]

    response = await client.post(f"/issues/{issue_id}/reply", headers=headers, json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_reply_without_token_fails(client, leader, member):
    """Ensure that replying is rejected without an access token"""
    _, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "No token reply test",
        "description": "Trying to reply without any authentication",
    }
    raised = await client.post("/issues", headers=member, json=payload)
    issue_id = raised.json()["id"]

    reply_payload = {"reply": "Should not be allowed"}
    response = await client.post(f"/issues/{issue_id}/reply", json=reply_payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# ==== resolve ====

@pytest.mark.asyncio
async def test_resolve_issue_success(client, leader, member):
    """Verify that a leader can resolve an issue"""
    headers, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Resolve test issue",
        "description": "This issue will be resolved by the leader",
    }
    raised = await client.post("/issues", headers=member, json=payload)
    issue_id = raised.json()["id"]

    response = await client.patch(f"/issues/{issue_id}/resolve", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == issue_id
    assert body["status"] == "RESOLVED"
    assert body["message"] == "Issue marked as resolved"

    listed = await client.get("/issues", headers=member)
    item = next(i for i in listed.json() if i["id"] == issue_id)
    assert item["resolved_at"] is not None


@pytest.mark.asyncio
async def test_resolve_issue_directly_from_open_succeeds(client, leader, member):
    """Confirm that an OPEN issue can be resolved directly without going through a reply first"""
    headers, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Direct resolve test",
        "description": "This issue skips the reply step and goes straight to resolved",
    }
    raised = await client.post("/issues", headers=member, json=payload)
    issue_id = raised.json()["id"]

    response = await client.patch(f"/issues/{issue_id}/resolve", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "RESOLVED"


@pytest.mark.asyncio
async def test_resolve_already_resolved_issue_fails(client, leader, member):
    """Confirm that resolving an already-resolved issue is rejected"""
    headers, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Double resolve test",
        "description": "This issue will be resolved more than once",
    }
    raised = await client.post("/issues", headers=member, json=payload)
    issue_id = raised.json()["id"]
    await client.patch(f"/issues/{issue_id}/resolve", headers=headers)

    response = await client.patch(f"/issues/{issue_id}/resolve", headers=headers)
    assert response.status_code == 403
    assert response.json()["message"] == "Issue is already resolved"


@pytest.mark.asyncio
async def test_resolve_unknown_issue_fails(client, leader):
    """Confirm that resolving a nonexistent issue returns not found"""
    headers, _ = leader
    response = await client.patch("/issues/999999/resolve", headers=headers)
    assert response.status_code == 404
    assert response.json()["message"] == "Issue not found"


@pytest.mark.asyncio
async def test_resolve_by_non_leader_fails(client, leader, member):
    """Ensure that a plain club member cannot resolve an issue"""
    _, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Non leader resolve test",
        "description": "A member should not be able to resolve this issue",
    }
    raised = await client.post("/issues", headers=member, json=payload)
    issue_id = raised.json()["id"]

    response = await client.patch(f"/issues/{issue_id}/resolve", headers=member)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_resolve_cross_college_issue_fails(client, leader, member):
    """Verify that resolving an issue belonging to a club from a different college returns not found"""
    other_admin_payload = {
        "email": "admin@otherissue.edu.in",
        "full_name": "Other Issue Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "CAMPUS_ADMIN",
    }
    other_admin_signup = await client.post("/auth/signup", json=other_admin_payload)
    other_admin_token = other_admin_signup.json()["access_token"]

    college_payload = {
        "name": "Other Issue College",
        "email_suffix": "otherissue.edu.in",
        "description": "A separate college for issue scoping tests",
    }
    await client.post(
        "/college/onboarding", json=college_payload,
        headers={"Authorization": f"Bearer {other_admin_token}"},
    )

    other_student_payload = {
        "email": "leader@otherissue.edu.in",
        "full_name": "Other Issue Leader",
        "password": "Leader@123",
        "confirm_password": "Leader@123",
        "role": "STUDENT",
    }
    other_student_signup = await client.post("/auth/signup", json=other_student_payload)
    other_headers = {"Authorization": f"Bearer {other_student_signup.json()['access_token']}"}

    club_payload = {
        "name": "Foreign Issue Club",
        "description": "A club that belongs to a different college",
        "category": "Technical",
        "type": "UNOFFICIAL",
    }
    other_club = await client.post("/clubs", headers=other_headers, json=club_payload)
    other_club_id = other_club.json()["id"]

    issue_payload = {
        "club_id": other_club_id,
        "category": "GENERAL",
        "title": "Foreign college issue",
        "description": "This issue belongs to a club in a different college",
    }
    raised = await client.post("/issues", headers=other_headers, json=issue_payload)
    issue_id = raised.json()["id"]

    headers, _ = leader
    response = await client.patch(f"/issues/{issue_id}/resolve", headers=headers)
    assert response.status_code == 404
    assert response.json()["message"] == "Issue not found"


@pytest.mark.asyncio
async def test_resolve_without_token_fails(client, leader, member):
    """Ensure that resolving is rejected without an access token"""
    _, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "No token resolve test",
        "description": "Trying to resolve without any authentication",
    }
    raised = await client.post("/issues", headers=member, json=payload)
    issue_id = raised.json()["id"]

    response = await client.patch(f"/issues/{issue_id}/resolve")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.asyncio
async def test_reply_cross_college_issue_fails(client, leader):
    """Verify that replying to an issue belonging to a club from a different college returns not found"""
    other_admin_payload = {
        "email": "admin@otherissuereply.edu.in",
        "full_name": "Other Issue Reply Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "CAMPUS_ADMIN",
    }
    other_admin_signup = await client.post("/auth/signup", json=other_admin_payload)
    other_admin_token = other_admin_signup.json()["access_token"]

    college_payload = {
        "name": "Other Issue Reply College",
        "email_suffix": "otherissuereply.edu.in",
        "description": "A separate college for issue reply scoping tests",
    }
    await client.post(
        "/college/onboarding", json=college_payload,
        headers={"Authorization": f"Bearer {other_admin_token}"},
    )

    other_student_payload = {
        "email": "leader@otherissuereply.edu.in",
        "full_name": "Other Issue Reply Leader",
        "password": "Leader@123",
        "confirm_password": "Leader@123",
        "role": "STUDENT",
    }
    other_student_signup = await client.post("/auth/signup", json=other_student_payload)
    other_headers = {"Authorization": f"Bearer {other_student_signup.json()['access_token']}"}

    club_payload = {
        "name": "Foreign Reply Club",
        "description": "A club that belongs to a different college",
        "category": "Technical",
        "type": "UNOFFICIAL",
    }
    other_club = await client.post("/clubs", headers=other_headers, json=club_payload)
    other_club_id = other_club.json()["id"]

    issue_payload = {
        "club_id": other_club_id,
        "category": "GENERAL",
        "title": "Foreign college reply target",
        "description": "This issue belongs to a club in a different college",
    }
    raised = await client.post("/issues", headers=other_headers, json=issue_payload)
    issue_id = raised.json()["id"]

    headers, _ = leader
    reply_payload = {"reply": "Trying to reply across colleges"}
    response = await client.post(f"/issues/{issue_id}/reply", headers=headers, json=reply_payload)
    assert response.status_code == 404
    assert response.json()["message"] == "Issue not found"


@pytest.mark.asyncio
async def test_reply_twice_updates_response_to_latest(client, leader, member):
    """Confirm that a second reply overwrites the response with the latest text, since only RESOLVED blocks replying"""
    headers, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Double reply test",
        "description": "This issue will receive two replies in a row",
    }
    raised = await client.post("/issues", headers=member, json=payload)
    issue_id = raised.json()["id"]

    first_reply = {"reply": "First response to this issue"}
    first = await client.post(f"/issues/{issue_id}/reply", headers=headers, json=first_reply)
    assert first.status_code == 200
    assert first.json()["status"] == "IN_PROGRESS"

    second_reply = {"reply": "Updated, corrected response"}
    second = await client.post(f"/issues/{issue_id}/reply", headers=headers, json=second_reply)
    assert second.status_code == 200
    assert second.json()["status"] == "IN_PROGRESS"

    listed = await client.get("/issues", headers=member)
    item = next(i for i in listed.json() if i["id"] == issue_id)
    assert item["response"]["text"] == "Updated, corrected response"


@pytest.mark.asyncio
async def test_reply_then_resolve_succeeds(client, leader, member):
    """Verify that an issue can move from IN_PROGRESS to RESOLVED after being replied to"""
    headers, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Reply then resolve test",
        "description": "This issue is replied to first, then resolved",
    }
    raised = await client.post("/issues", headers=member, json=payload)
    issue_id = raised.json()["id"]

    reply_payload = {"reply": "We are on it"}
    await client.post(f"/issues/{issue_id}/reply", headers=headers, json=reply_payload)

    response = await client.patch(f"/issues/{issue_id}/resolve", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "RESOLVED"


@pytest.mark.asyncio
async def test_club_queue_club_id_for_unled_club_returns_empty(client, leader, member):
    """Confirm that filtering the club queue by a club_id the caller doesn't lead returns an empty list, not another leader's issues"""
    headers, club_id = leader
    other_leader_payload = {
        "email": "otherclubqueueleader@knit.edu.in",
        "full_name": "Other Queue Leader",
        "password": "Test@1234",
        "confirm_password": "Test@1234",
        "role": "STUDENT",
    }
    signup = await client.post("/auth/signup", json=other_leader_payload)
    other_headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    other_club_payload = {
        "name": "Unled Queue Club",
        "description": "A club the requesting leader does not lead",
        "category": "Technical",
        "type": "UNOFFICIAL",
    }
    other_club = await client.post("/clubs", headers=other_headers, json=other_club_payload)
    other_club_id = other_club.json()["id"]

    issue_payload = {
        "club_id": other_club_id,
        "category": "GENERAL",
        "title": "Issue in a club the caller does not lead",
        "description": "This should never appear in the original leader's filtered queue",
    }
    await client.post("/issues", headers=other_headers, json=issue_payload)

    response = await client.get("/issues/club", headers=headers, params={"club_id": other_club_id})
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_open_count_aggregates_across_multiple_led_clubs(client, leader, member):
    """Verify that open-count sums unresolved issues across every club the student leads, not just one"""
    headers, first_club_id = leader
    second_club_payload = {
        "name": "Second Led Club",
        "description": "A second club led by the same student",
        "category": "Arts",
        "type": "UNOFFICIAL",
    }
    second_club = await client.post("/clubs", headers=headers, json=second_club_payload)
    second_club_id = second_club.json()["id"]

    before = await client.get("/issues/club/open-count", headers=headers)
    initial_count = before.json()["count"]

    first_payload = {
        "club_id": first_club_id,
        "category": "GENERAL",
        "title": "Issue in first led club",
        "description": "An unresolved issue in the first club the student leads",
    }
    await client.post("/issues", headers=member, json=first_payload)

    second_payload = {
        "club_id": second_club_id,
        "category": "GENERAL",
        "title": "Issue in second led club",
        "description": "An unresolved issue in the second club the student leads",
    }
    await client.post("/issues", headers=member, json=second_payload)

    after = await client.get("/issues/club/open-count", headers=headers)
    assert after.json()["count"] == initial_count + 2


@pytest.mark.asyncio
async def test_my_issues_event_id_is_none_when_not_provided(client, leader, member):
    """Confirm that event_id is null in the response when the issue was raised without one"""
    _, club_id = leader
    payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "No event reference issue",
        "description": "This issue was raised without an associated event",
    }
    raised = await client.post("/issues", headers=member, json=payload)
    issue_id = raised.json()["id"]

    listed = await client.get("/issues", headers=member)
    item = next(i for i in listed.json() if i["id"] == issue_id)
    assert item["event_id"] is None


@pytest.mark.asyncio
async def test_my_issues_limit_caps_returned_items(client, leader, member):
    """Confirm that limit actually caps the number of issues returned, not just accepted"""
    _, club_id = leader
    for i in range(3):
        payload = {
            "club_id": club_id,
            "category": "GENERAL",
            "title": f"Pagination issue {i}",
            "description": f"Issue number {i} used to test the limit cap",
        }
        await client.post("/issues", headers=member, json=payload)

    response = await client.get("/issues", headers=member, params={"limit": 1})
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_raise_issue_against_draft_event_succeeds(client, leader, member):
    """Confirm that an issue can be raised against a draft, unpublished event since no status check exists"""
    headers, club_id = leader
    event_payload = {
        "club_id": club_id,
        "title": "Unpublished Workshop",
        "description": "An event that has never been published",
        "venue": "Lab 204",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    event = await client.post("/events", headers=headers, json=event_payload)
    event_id = event.json()["id"]

    payload = {
        "club_id": club_id,
        "category": "EVENT",
        "title": "Issue against draft event",
        "description": "This event has never been published but the issue should still be accepted",
        "event_id": event_id,
    }
    response = await client.post("/issues", headers=member, json=payload)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_raise_issue_against_past_event_succeeds(client, db_session, leader, member):
    """Confirm that an issue can be raised against an event whose window has already ended"""
    from datetime import datetime, timedelta, timezone
    from app.models import Event

    headers, club_id = leader
    event_payload = {
        "club_id": club_id,
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
        "club_id": club_id,
        "category": "EVENT",
        "title": "Issue against concluded event",
        "description": "This event has already ended but the issue should still be accepted",
        "event_id": event_id,
    }
    response = await client.post("/issues", headers=member, json=payload)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_raise_issue_by_non_registrant_succeeds(client, leader, member):
    """Confirm that a student can raise an issue against an event they never registered for"""
    headers, club_id = leader
    event_payload = {
        "club_id": club_id,
        "title": "Never Registered Workshop",
        "description": "An event the issue-raiser never signs up for",
        "venue": "Lab 204",
        "starts_at": future_time(48),
        "ends_at": future_time(50),
    }
    event = await client.post("/events", headers=headers, json=event_payload)
    event_id = event.json()["id"]
    await client.patch(f"/events/{event_id}/publish", headers=headers)

    payload = {
        "club_id": club_id,
        "category": "EVENT",
        "title": "Issue without registering first",
        "description": "This student never registered for the event but still has a question about it",
        "event_id": event_id,
    }
    response = await client.post("/issues", headers=member, json=payload)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_club_queue_open_sorts_before_in_progress(client, leader, member):
    """Confirm that OPEN issues sort before IN_PROGRESS ones in the leader queue, since status is a native Postgres enum ordered by declaration position, not alphabetically"""
    headers, club_id = leader
    open_payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Still open issue",
        "description": "This issue remains untouched in the OPEN status",
    }
    open_issue = await client.post("/issues", headers=member, json=open_payload)
    open_id = open_issue.json()["id"]

    in_progress_payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "In progress issue",
        "description": "This issue will be replied to, moving it to IN_PROGRESS",
    }
    in_progress_issue = await client.post("/issues", headers=member, json=in_progress_payload)
    in_progress_id = in_progress_issue.json()["id"]
    reply_payload = {"reply": "Working on this one"}
    await client.post(f"/issues/{in_progress_id}/reply", headers=headers, json=reply_payload)

    response = await client.get("/issues/club", headers=headers)
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]

    assert ids.index(open_id) < ids.index(in_progress_id)

@pytest.mark.asyncio
async def test_club_queue_full_status_order_open_in_progress_resolved(client, leader, member):
    """Confirm the full native-enum ordering: OPEN, then IN_PROGRESS, then RESOLVED"""
    headers, club_id = leader

    resolved_payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Will be resolved",
        "description": "This issue will be resolved directly",
    }
    resolved_issue = await client.post("/issues", headers=member, json=resolved_payload)
    resolved_id = resolved_issue.json()["id"]
    await client.patch(f"/issues/{resolved_id}/resolve", headers=headers)

    in_progress_payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Will be in progress",
        "description": "This issue will be replied to but not resolved",
    }
    in_progress_issue = await client.post("/issues", headers=member, json=in_progress_payload)
    in_progress_id = in_progress_issue.json()["id"]
    await client.post(f"/issues/{in_progress_id}/reply", headers=headers, json={"reply": "On it"})

    open_payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Stays open",
        "description": "This issue is left untouched in the OPEN status",
    }
    open_issue = await client.post("/issues", headers=member, json=open_payload)
    open_id = open_issue.json()["id"]

    response = await client.get("/issues/club", headers=headers)
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert ids.index(open_id) < ids.index(in_progress_id) < ids.index(resolved_id)

@pytest.mark.asyncio
async def test_club_queue_same_status_sorts_oldest_first(client, db_session, leader, member):
    """Confirm that within the same status, the club queue orders oldest-first, unlike other feeds in the app which sort newest-first"""
    from datetime import datetime, timedelta
    from app.models import Issue

    headers, club_id = leader
    first_payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Raised first",
        "description": "This issue is raised before the second one",
    }
    first_issue = await client.post("/issues", headers=member, json=first_payload)
    first_id = first_issue.json()["id"]

    second_payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "Raised second",
        "description": "This issue is raised after the first one",
    }
    second_issue = await client.post("/issues", headers=member, json=second_payload)
    second_id = second_issue.json()["id"]

    # force distinct timestamps — same-transaction func.now() can otherwise tie
    issue_row = await db_session.get(Issue, second_id)
    issue_row.created_at = datetime.now() + timedelta(seconds=5)
    await db_session.flush()

    response = await client.get("/issues/club", headers=headers)
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert ids.index(first_id) < ids.index(second_id)

@pytest.mark.asyncio
async def test_my_issues_sorts_newest_first(client, db_session, leader, member):
    """Confirm that a student's own issue list sorts newest-first, in contrast to the leader queue's oldest-first ordering"""
    from datetime import datetime, timedelta
    from app.models import Issue

    _, club_id = leader
    first_payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "My first issue",
        "description": "Raised before the second issue",
    }
    first_issue = await client.post("/issues", headers=member, json=first_payload)
    first_id = first_issue.json()["id"]

    second_payload = {
        "club_id": club_id,
        "category": "GENERAL",
        "title": "My second issue",
        "description": "Raised after the first issue",
    }
    second_issue = await client.post("/issues", headers=member, json=second_payload)
    second_id = second_issue.json()["id"]

    issue_row = await db_session.get(Issue, second_id)
    issue_row.created_at = datetime.now() + timedelta(seconds=5)
    await db_session.flush()

    response = await client.get("/issues", headers=member)
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert ids.index(second_id) < ids.index(first_id)