import pytest


# ==== join ====

@pytest.mark.asyncio
async def test_join_active_club_success(client, student_token):
    """Verify that a student can request to join an ACTIVE club"""
    club_payload = {
        "name": "Joinable Club",
        "description": "A club that is active and open for join requests",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=club_payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]

    joiner_payload = {
        "email": "joiner.one@knit.edu.in",
        "full_name": "Joiner One",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "STUDENT"
    }
    joiner_signup = await client.post("/auth/signup", json=joiner_payload)
    joiner_token = joiner_signup.json()["access_token"]

    response = await client.post(f"/clubs/{club_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["club_id"] == club_id
    assert body["status"] == "PENDING"
    assert body["message"] == "Join request sent"


@pytest.mark.asyncio
async def test_join_club_that_is_pending_fails(client, student_token):
    """Verify that joining a club is rejected when the club status is PENDING"""
    club_payload = {
        "name": "Pending Join Club",
        "description": "A club left pending to test join rejection",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    create = await client.post("/clubs", json=club_payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]

    joiner_payload = {
        "email": "joiner.pending@knit.edu.in",
        "full_name": "Joiner Pending",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "STUDENT"
    }
    joiner_signup = await client.post("/auth/signup", json=joiner_payload)
    joiner_token = joiner_signup.json()["access_token"]

    response = await client.post(f"/clubs/{club_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})
    assert response.status_code == 403
    body = response.json()
    assert body["message"] == "Club is not active"


@pytest.mark.asyncio
async def test_join_club_that_is_archived_fails(client, student_token):
    """Verify that joining a club is rejected when the club status is ARCHIVED"""
    club_payload = {
        "name": "Archived Join Club",
        "description": "A club that will be archived before a join attempt",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=club_payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]
    await client.delete(f"/clubs/{club_id}", headers={"Authorization": f"Bearer {student_token}"})

    joiner_payload = {
        "email": "joiner.archived@knit.edu.in",
        "full_name": "Joiner Archived",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "STUDENT"
    }
    joiner_signup = await client.post("/auth/signup", json=joiner_payload)
    joiner_token = joiner_signup.json()["access_token"]

    response = await client.post(f"/clubs/{club_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})
    assert response.status_code == 403
    body = response.json()
    assert body["message"] == "Club is not active"


@pytest.mark.asyncio
async def test_join_already_member_fails(client, student_token):
    """Verify that a student who already has a membership or request for a club cannot join again"""
    club_payload = {
        "name": "Double Join Club",
        "description": "A club used to test duplicate join rejection",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=club_payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]

    joiner_payload = {
        "email": "joiner.twice@knit.edu.in",
        "full_name": "Joiner Twice",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "STUDENT"
    }
    joiner_signup = await client.post("/auth/signup", json=joiner_payload)
    joiner_token = joiner_signup.json()["access_token"]

    await client.post(f"/clubs/{club_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})
    response = await client.post(f"/clubs/{club_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})
    assert response.status_code == 409
    body = response.json()
    assert body["message"] == "You already have a membership or request for this club"


@pytest.mark.asyncio
async def test_join_club_leader_cannot_join_own_club_again_fails(client, student_token):
    """Confirm that the club leader cannot send a join request for a club they already lead"""
    club_payload = {
        "name": "Leader Rejoin Club",
        "description": "A club used to test that the leader cannot rejoin their own club",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=club_payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]

    response = await client.post(f"/clubs/{club_id}/join", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 409
    body = response.json()
    assert body["message"] == "You already have a membership or request for this club"


@pytest.mark.asyncio
async def test_join_nonexistent_club_returns_404(client, student_token):
    """Verify that joining a nonexistent club returns not found"""
    response = await client.post("/clubs/999999/join", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Club not found"


@pytest.mark.asyncio
async def test_join_club_without_token_fails(client, student_token):
    """Verify that joining a club is rejected when no authentication token is provided"""
    club_payload = {
        "name": "No Token Join Club",
        "description": "A club used to test unauthenticated join access",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=club_payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]

    response = await client.post(f"/clubs/{club_id}/join")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# ==== pending requests ====

@pytest.mark.asyncio
async def test_view_pending_requests_by_leader_success(client, student_token):
    """Verify that the club leader can view pending join requests"""
    club_payload = {
        "name": "Requests Visible Club",
        "description": "A club used to test viewing pending requests as leader",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=club_payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]

    joiner_payload = {
        "email": "joiner.pendingview@knit.edu.in",
        "full_name": "Joiner Pending View",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "STUDENT"
    }
    joiner_signup = await client.post("/auth/signup", json=joiner_payload)
    joiner_token = joiner_signup.json()["access_token"]
    await client.post(f"/clubs/{club_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})

    response = await client.get(f"/clubs/{club_id}/requests", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    body = response.json()
    names = [item["full_name"] for item in body]
    assert "Joiner Pending View" in names


@pytest.mark.asyncio
async def test_pending_requests_by_non_leader_fails(client, student_token):
    """Verify that a non-leader student cannot view pending join requests"""
    club_payload = {
        "name": "Requests Hidden Club",
        "description": "A club used to test that non-leaders cannot view requests",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=club_payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]

    other_payload = {
        "email": "outsider.requests@knit.edu.in",
        "full_name": "Outsider Requests",
        "password": "Outsider@123",
        "confirm_password": "Outsider@123",
        "role": "STUDENT"
    }
    other_signup = await client.post("/auth/signup", json=other_payload)
    other_token = other_signup.json()["access_token"]

    response = await client.get(f"/clubs/{club_id}/requests", headers={"Authorization": f"Bearer {other_token}"})
    assert response.status_code == 403
    body = response.json()
    assert body["message"] == "Only the club leader can perform this action"


@pytest.mark.asyncio
async def test_pending_requests_ordered_by_creation_time(client, student_token):
    """Verify that pending requests are returned in ascending order of creation"""
    club_payload = {
        "name": "Ordered Requests Club",
        "description": "A club used to test pending request ordering",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=club_payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]

    first_joiner_payload = {
        "email": "joiner.first@knit.edu.in",
        "full_name": "Joiner First",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "STUDENT"
    }
    first_signup = await client.post("/auth/signup", json=first_joiner_payload)
    first_token = first_signup.json()["access_token"]
    await client.post(f"/clubs/{club_id}/join", headers={"Authorization": f"Bearer {first_token}"})

    second_joiner_payload = {
        "email": "joiner.second@knit.edu.in",
        "full_name": "Joiner Second",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "STUDENT"
    }
    second_signup = await client.post("/auth/signup", json=second_joiner_payload)
    second_token = second_signup.json()["access_token"]
    await client.post(f"/clubs/{club_id}/join", headers={"Authorization": f"Bearer {second_token}"})

    response = await client.get(f"/clubs/{club_id}/requests", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    names = [item["full_name"] for item in response.json()]
    assert names.index("Joiner First") < names.index("Joiner Second")


@pytest.mark.asyncio
async def test_pending_requests_for_nonexistent_club_returns_empty_or_404(client, student_token):
    """Verify that viewing pending requests for a nonexistent club does not return other clubs' requests"""
    response = await client.get("/clubs/999999/requests", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 403
    body = response.json()
    assert body["message"] == "Only the club leader can perform this action"


@pytest.mark.asyncio
async def test_pending_requests_without_token_fails(client, student_token):
    """Verify that viewing pending requests is rejected when no authentication token is provided"""
    club_payload = {
        "name": "No Token Requests Club",
        "description": "A club used to test unauthenticated pending requests access",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=club_payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]

    response = await client.get(f"/clubs/{club_id}/requests")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# ==== handle request (approve/reject) ====

@pytest.mark.asyncio
async def test_approve_join_request_success(client, student_token):
    """Verify that the club leader can approve a pending join request"""
    club_payload = {
        "name": "Approve Request Club",
        "description": "A club used to test approving a join request",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=club_payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]

    joiner_payload = {
        "email": "joiner.approve@knit.edu.in",
        "full_name": "Joiner Approve",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "STUDENT"
    }
    joiner_signup = await client.post("/auth/signup", json=joiner_payload)
    joiner_token = joiner_signup.json()["access_token"]
    join = await client.post(f"/clubs/{club_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})
    membership_id = join.json()["id"]

    action_payload = {"action": "APPROVED"}
    response = await client.patch(
        f"/clubs/{club_id}/requests/{membership_id}",
        json=action_payload,
        headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "APPROVED"
    assert body["message"] == "Join request approved"


@pytest.mark.asyncio
async def test_reject_join_request_success(client, student_token):
    """Verify that the club leader can reject a pending join request"""
    club_payload = {
        "name": "Reject Request Club",
        "description": "A club used to test rejecting a join request",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=club_payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]

    joiner_payload = {
        "email": "joiner.reject@knit.edu.in",
        "full_name": "Joiner Reject",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "STUDENT"
    }
    joiner_signup = await client.post("/auth/signup", json=joiner_payload)
    joiner_token = joiner_signup.json()["access_token"]
    join = await client.post(f"/clubs/{club_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})
    membership_id = join.json()["id"]

    action_payload = {"action": "REJECTED"}
    response = await client.patch(
        f"/clubs/{club_id}/requests/{membership_id}",
        json=action_payload,
        headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "REJECTED"
    assert body["message"] == "Join request rejected"


@pytest.mark.asyncio
async def test_handle_request_by_non_leader_fails(client, student_token):
    """Verify that a non-leader student cannot approve or reject a join request"""
    club_payload = {
        "name": "Non Leader Handle Club",
        "description": "A club used to test that non-leaders cannot handle requests",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=club_payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]

    joiner_payload = {
        "email": "joiner.nonleader@knit.edu.in",
        "full_name": "Joiner Non Leader",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "STUDENT"
    }
    joiner_signup = await client.post("/auth/signup", json=joiner_payload)
    joiner_token = joiner_signup.json()["access_token"]
    join = await client.post(f"/clubs/{club_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})
    membership_id = join.json()["id"]

    outsider_payload = {
        "email": "outsider.handle@knit.edu.in",
        "full_name": "Outsider Handle",
        "password": "Outsider@123",
        "confirm_password": "Outsider@123",
        "role": "STUDENT"
    }
    outsider_signup = await client.post("/auth/signup", json=outsider_payload)
    outsider_token = outsider_signup.json()["access_token"]

    action_payload = {"action": "APPROVED"}
    response = await client.patch(
        f"/clubs/{club_id}/requests/{membership_id}",
        json=action_payload,
        headers={"Authorization": f"Bearer {outsider_token}"}
    )
    assert response.status_code == 403
    body = response.json()
    assert body["message"] == "Only the club leader can perform this action"


@pytest.mark.asyncio
async def test_handle_already_handled_request_fails(client, student_token):
    """Confirm that acting on a membership request that is no longer PENDING is rejected"""
    club_payload = {
        "name": "Already Handled Club",
        "description": "A club used to test rejecting an already-handled request",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=club_payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]

    joiner_payload = {
        "email": "joiner.alreadyhandled@knit.edu.in",
        "full_name": "Joiner Already Handled",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "STUDENT"
    }
    joiner_signup = await client.post("/auth/signup", json=joiner_payload)
    joiner_token = joiner_signup.json()["access_token"]
    join = await client.post(f"/clubs/{club_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})
    membership_id = join.json()["id"]

    action_payload = {"action": "APPROVED"}
    await client.patch(
        f"/clubs/{club_id}/requests/{membership_id}",
        json=action_payload,
        headers={"Authorization": f"Bearer {student_token}"}
    )
    response = await client.patch(
        f"/clubs/{club_id}/requests/{membership_id}",
        json=action_payload,
        headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 403
    body = response.json()
    assert body["message"] == "Request has already been handled"


@pytest.mark.asyncio
async def test_handle_request_from_different_club_fails(client, student_token):
    """Verify that acting on a membership belonging to a different club_id than specified in the URL is rejected"""
    first_club_payload = {
        "name": "First Handle Club",
        "description": "The club the join request actually belongs to",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    first_create = await client.post(
        "/clubs", json=first_club_payload, headers={"Authorization": f"Bearer {student_token}"}
    )
    first_club_id = first_create.json()["id"]

    second_club_payload = {
        "name": "Second Handle Club",
        "description": "A different club used as the wrong club_id in the URL",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    second_create = await client.post(
        "/clubs", json=second_club_payload, headers={"Authorization": f"Bearer {student_token}"}
    )
    second_club_id = second_create.json()["id"]

    joiner_payload = {
        "email": "joiner.wrongclub@knit.edu.in",
        "full_name": "Joiner Wrong Club",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "STUDENT"
    }
    joiner_signup = await client.post("/auth/signup", json=joiner_payload)
    joiner_token = joiner_signup.json()["access_token"]
    join = await client.post(f"/clubs/{first_club_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})
    membership_id = join.json()["id"]

    action_payload = {"action": "APPROVED"}
    response = await client.patch(
        f"/clubs/{second_club_id}/requests/{membership_id}",
        json=action_payload,
        headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Membership request not found"


@pytest.mark.asyncio
async def test_handle_nonexistent_request_returns_404(client, student_token):
    """Verify that handling a nonexistent membership id returns not found"""
    club_payload = {
        "name": "Nonexistent Request Club",
        "description": "A club used to test handling a nonexistent membership request",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=club_payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]

    action_payload = {"action": "APPROVED"}
    response = await client.patch(
        f"/clubs/{club_id}/requests/999999",
        json=action_payload,
        headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Membership request not found"


@pytest.mark.asyncio
async def test_handle_request_invalid_action_value_fails(client, student_token):
    """Validate that handling a join request is rejected when the action value is not a recognized enum"""
    club_payload = {
        "name": "Invalid Action Club",
        "description": "A club used to test rejection of an invalid action value",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=club_payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]

    joiner_payload = {
        "email": "joiner.invalidaction@knit.edu.in",
        "full_name": "Joiner Invalid Action",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "STUDENT"
    }
    joiner_signup = await client.post("/auth/signup", json=joiner_payload)
    joiner_token = joiner_signup.json()["access_token"]
    join = await client.post(f"/clubs/{club_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})
    membership_id = join.json()["id"]

    action_payload = {"action": "MAYBE"}
    response = await client.patch(
        f"/clubs/{club_id}/requests/{membership_id}",
        json=action_payload,
        headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_handle_request_without_token_fails(client, student_token):
    """Verify that handling a join request is rejected when no authentication token is provided"""
    club_payload = {
        "name": "No Token Handle Club",
        "description": "A club used to test unauthenticated handle request access",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=club_payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]

    joiner_payload = {
        "email": "joiner.notoken@knit.edu.in",
        "full_name": "Joiner No Token",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "STUDENT"
    }
    joiner_signup = await client.post("/auth/signup", json=joiner_payload)
    joiner_token = joiner_signup.json()["access_token"]
    join = await client.post(f"/clubs/{club_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})
    membership_id = join.json()["id"]

    action_payload = {"action": "APPROVED"}
    response = await client.patch(f"/clubs/{club_id}/requests/{membership_id}", json=action_payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# ==== members ====

@pytest.mark.asyncio
async def test_view_club_members_success(client, student_token):
    """Verify that club members can be listed, showing only approved memberships"""
    club_payload = {
        "name": "Members List Club",
        "description": "A club used to test listing approved members",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=club_payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]

    joiner_payload = {
        "email": "joiner.memberslist@knit.edu.in",
        "full_name": "Joiner Members List",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "STUDENT"
    }
    joiner_signup = await client.post("/auth/signup", json=joiner_payload)
    joiner_token = joiner_signup.json()["access_token"]
    join = await client.post(f"/clubs/{club_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})
    membership_id = join.json()["id"]

    action_payload = {"action": "APPROVED"}
    await client.patch(
        f"/clubs/{club_id}/requests/{membership_id}",
        json=action_payload,
        headers={"Authorization": f"Bearer {student_token}"}
    )

    response = await client.get(f"/clubs/{club_id}/members", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    names = [member["full_name"] for member in response.json()]
    assert "Joiner Members List" in names


@pytest.mark.asyncio
async def test_members_list_excludes_pending_and_rejected(client, student_token):
    """Confirm that the members list only includes APPROVED memberships, excluding PENDING or REJECTED ones"""
    club_payload = {
        "name": "Members Exclusion Club",
        "description": "A club used to test that pending and rejected memberships are excluded",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=club_payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]

    pending_payload = {
        "email": "joiner.stillpending@knit.edu.in",
        "full_name": "Joiner Still Pending",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "STUDENT"
    }
    pending_signup = await client.post("/auth/signup", json=pending_payload)
    pending_token = pending_signup.json()["access_token"]
    await client.post(f"/clubs/{club_id}/join", headers={"Authorization": f"Bearer {pending_token}"})

    rejected_payload = {
        "email": "joiner.gotrejected@knit.edu.in",
        "full_name": "Joiner Got Rejected",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "STUDENT"
    }
    rejected_signup = await client.post("/auth/signup", json=rejected_payload)
    rejected_token = rejected_signup.json()["access_token"]
    rejected_join = await client.post(f"/clubs/{club_id}/join", headers={"Authorization": f"Bearer {rejected_token}"})
    rejected_membership_id = rejected_join.json()["id"]
    await client.patch(
        f"/clubs/{club_id}/requests/{rejected_membership_id}",
        json={"action": "REJECTED"},
        headers={"Authorization": f"Bearer {student_token}"}
    )

    response = await client.get(f"/clubs/{club_id}/members", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    names = [member["full_name"] for member in response.json()]
    assert "Joiner Still Pending" not in names
    assert "Joiner Got Rejected" not in names


@pytest.mark.asyncio
async def test_members_list_includes_leader(client, student_token):
    """Verify that the club leader appears in the members list as an approved member"""
    club_payload = {
        "name": "Leader Members Club",
        "description": "A club used to test that the leader appears in the members list",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=club_payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]

    response = await client.get(f"/clubs/{club_id}/members", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    roles = [member["role"] for member in response.json()]
    assert "LEADER" in roles


@pytest.mark.asyncio
async def test_members_list_for_nonexistent_club_returns_404(client, student_token):
    """Verify that listing members for a nonexistent club returns not found"""
    response = await client.get("/clubs/999999/members", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Club not found"


@pytest.mark.asyncio
async def test_members_without_token_fails(client, student_token):
    """Verify that listing club members is rejected when no authentication token is provided"""
    club_payload = {
        "name": "No Token Members Club",
        "description": "A club used to test unauthenticated members access",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=club_payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]

    response = await client.get(f"/clubs/{club_id}/members")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"