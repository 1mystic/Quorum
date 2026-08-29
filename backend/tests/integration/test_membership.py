import pytest


# ==== join ====

@pytest.mark.asyncio
async def test_join_active_group_success(client, member_token):
    """Verify that a member can request to join an ACTIVE group"""
    group_payload = {
        "name": "Joinable Group",
        "description": "A group that is active and open for join requests",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=group_payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]

    joiner_payload = {
        "email": "joiner.one@knit.edu.in",
        "full_name": "Joiner One",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "MEMBER"
    }
    joiner_signup = await client.post("/auth/signup", json=joiner_payload)
    joiner_token = joiner_signup.json()["access_token"]

    response = await client.post(f"/groups/{group_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["group_id"] == group_id
    assert body["status"] == "PENDING"
    assert body["message"] == "Join request sent"


@pytest.mark.asyncio
async def test_join_group_that_is_pending_fails(client, member_token):
    """Verify that joining a group is rejected when the group status is PENDING"""
    group_payload = {
        "name": "Pending Join Group",
        "description": "A group left pending to test join rejection",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    create = await client.post("/groups", json=group_payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]

    joiner_payload = {
        "email": "joiner.pending@knit.edu.in",
        "full_name": "Joiner Pending",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "MEMBER"
    }
    joiner_signup = await client.post("/auth/signup", json=joiner_payload)
    joiner_token = joiner_signup.json()["access_token"]

    response = await client.post(f"/groups/{group_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})
    assert response.status_code == 403
    body = response.json()
    assert body["message"] == "Group is not active"


@pytest.mark.asyncio
async def test_join_group_that_is_archived_fails(client, member_token):
    """Verify that joining a group is rejected when the group status is ARCHIVED"""
    group_payload = {
        "name": "Archived Join Group",
        "description": "A group that will be archived before a join attempt",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=group_payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]
    await client.delete(f"/groups/{group_id}", headers={"Authorization": f"Bearer {member_token}"})

    joiner_payload = {
        "email": "joiner.archived@knit.edu.in",
        "full_name": "Joiner Archived",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "MEMBER"
    }
    joiner_signup = await client.post("/auth/signup", json=joiner_payload)
    joiner_token = joiner_signup.json()["access_token"]

    response = await client.post(f"/groups/{group_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})
    assert response.status_code == 403
    body = response.json()
    assert body["message"] == "Group is not active"


@pytest.mark.asyncio
async def test_join_already_member_fails(client, member_token):
    """Verify that a member who already has a membership or request for a group cannot join again"""
    group_payload = {
        "name": "Double Join Group",
        "description": "A group used to test duplicate join rejection",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=group_payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]

    joiner_payload = {
        "email": "joiner.twice@knit.edu.in",
        "full_name": "Joiner Twice",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "MEMBER"
    }
    joiner_signup = await client.post("/auth/signup", json=joiner_payload)
    joiner_token = joiner_signup.json()["access_token"]

    await client.post(f"/groups/{group_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})
    response = await client.post(f"/groups/{group_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})
    assert response.status_code == 409
    body = response.json()
    assert body["message"] == "You already have a membership or request for this group"


@pytest.mark.asyncio
async def test_join_group_leader_cannot_join_own_group_again_fails(client, member_token):
    """Confirm that the group leader cannot send a join request for a group they already lead"""
    group_payload = {
        "name": "Leader Rejoin Group",
        "description": "A group used to test that the leader cannot rejoin their own group",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=group_payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]

    response = await client.post(f"/groups/{group_id}/join", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 409
    body = response.json()
    assert body["message"] == "You already have a membership or request for this group"


@pytest.mark.asyncio
async def test_join_nonexistent_group_returns_404(client, member_token):
    """Verify that joining a nonexistent group returns not found"""
    response = await client.post("/groups/999999/join", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Group not found"


@pytest.mark.asyncio
async def test_join_group_without_token_fails(client, member_token):
    """Verify that joining a group is rejected when no authentication token is provided"""
    group_payload = {
        "name": "No Token Join Group",
        "description": "A group used to test unauthenticated join access",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=group_payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]

    response = await client.post(f"/groups/{group_id}/join")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# ==== pending requests ====

@pytest.mark.asyncio
async def test_view_pending_requests_by_leader_success(client, member_token):
    """Verify that the group leader can view pending join requests"""
    group_payload = {
        "name": "Requests Visible Group",
        "description": "A group used to test viewing pending requests as leader",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=group_payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]

    joiner_payload = {
        "email": "joiner.pendingview@knit.edu.in",
        "full_name": "Joiner Pending View",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "MEMBER"
    }
    joiner_signup = await client.post("/auth/signup", json=joiner_payload)
    joiner_token = joiner_signup.json()["access_token"]
    await client.post(f"/groups/{group_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})

    response = await client.get(f"/groups/{group_id}/requests", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    body = response.json()
    names = [item["full_name"] for item in body]
    assert "Joiner Pending View" in names


@pytest.mark.asyncio
async def test_pending_requests_by_non_leader_fails(client, member_token):
    """Verify that a non-leader member cannot view pending join requests"""
    group_payload = {
        "name": "Requests Hidden Group",
        "description": "A group used to test that non-leaders cannot view requests",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=group_payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]

    other_payload = {
        "email": "outsider.requests@knit.edu.in",
        "full_name": "Outsider Requests",
        "password": "Outsider@123",
        "confirm_password": "Outsider@123",
        "role": "MEMBER"
    }
    other_signup = await client.post("/auth/signup", json=other_payload)
    other_token = other_signup.json()["access_token"]

    response = await client.get(f"/groups/{group_id}/requests", headers={"Authorization": f"Bearer {other_token}"})
    assert response.status_code == 403
    body = response.json()
    assert body["message"] == "Only the group leader can perform this action"


@pytest.mark.asyncio
async def test_pending_requests_ordered_by_creation_time(client, member_token):
    """Verify that pending requests are returned in ascending order of creation"""
    group_payload = {
        "name": "Ordered Requests Group",
        "description": "A group used to test pending request ordering",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=group_payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]

    first_joiner_payload = {
        "email": "joiner.first@knit.edu.in",
        "full_name": "Joiner First",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "MEMBER"
    }
    first_signup = await client.post("/auth/signup", json=first_joiner_payload)
    first_token = first_signup.json()["access_token"]
    await client.post(f"/groups/{group_id}/join", headers={"Authorization": f"Bearer {first_token}"})

    second_joiner_payload = {
        "email": "joiner.second@knit.edu.in",
        "full_name": "Joiner Second",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "MEMBER"
    }
    second_signup = await client.post("/auth/signup", json=second_joiner_payload)
    second_token = second_signup.json()["access_token"]
    await client.post(f"/groups/{group_id}/join", headers={"Authorization": f"Bearer {second_token}"})

    response = await client.get(f"/groups/{group_id}/requests", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    names = [item["full_name"] for item in response.json()]
    assert names.index("Joiner First") < names.index("Joiner Second")


@pytest.mark.asyncio
async def test_pending_requests_for_nonexistent_group_returns_empty_or_404(client, member_token):
    """Verify that viewing pending requests for a nonexistent group does not return other groups' requests"""
    response = await client.get("/groups/999999/requests", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 403
    body = response.json()
    assert body["message"] == "Only the group leader can perform this action"


@pytest.mark.asyncio
async def test_pending_requests_without_token_fails(client, member_token):
    """Verify that viewing pending requests is rejected when no authentication token is provided"""
    group_payload = {
        "name": "No Token Requests Group",
        "description": "A group used to test unauthenticated pending requests access",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=group_payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]

    response = await client.get(f"/groups/{group_id}/requests")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# ==== handle request (approve/reject) ====

@pytest.mark.asyncio
async def test_approve_join_request_success(client, member_token):
    """Verify that the group leader can approve a pending join request"""
    group_payload = {
        "name": "Approve Request Group",
        "description": "A group used to test approving a join request",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=group_payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]

    joiner_payload = {
        "email": "joiner.approve@knit.edu.in",
        "full_name": "Joiner Approve",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "MEMBER"
    }
    joiner_signup = await client.post("/auth/signup", json=joiner_payload)
    joiner_token = joiner_signup.json()["access_token"]
    join = await client.post(f"/groups/{group_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})
    membership_id = join.json()["id"]

    action_payload = {"action": "APPROVED"}
    response = await client.patch(
        f"/groups/{group_id}/requests/{membership_id}",
        json=action_payload,
        headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "APPROVED"
    assert body["message"] == "Join request approved"


@pytest.mark.asyncio
async def test_reject_join_request_success(client, member_token):
    """Verify that the group leader can reject a pending join request"""
    group_payload = {
        "name": "Reject Request Group",
        "description": "A group used to test rejecting a join request",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=group_payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]

    joiner_payload = {
        "email": "joiner.reject@knit.edu.in",
        "full_name": "Joiner Reject",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "MEMBER"
    }
    joiner_signup = await client.post("/auth/signup", json=joiner_payload)
    joiner_token = joiner_signup.json()["access_token"]
    join = await client.post(f"/groups/{group_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})
    membership_id = join.json()["id"]

    action_payload = {"action": "REJECTED"}
    response = await client.patch(
        f"/groups/{group_id}/requests/{membership_id}",
        json=action_payload,
        headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "REJECTED"
    assert body["message"] == "Join request rejected"


@pytest.mark.asyncio
async def test_handle_request_by_non_leader_fails(client, member_token):
    """Verify that a non-leader member cannot approve or reject a join request"""
    group_payload = {
        "name": "Non Leader Handle Group",
        "description": "A group used to test that non-leaders cannot handle requests",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=group_payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]

    joiner_payload = {
        "email": "joiner.nonleader@knit.edu.in",
        "full_name": "Joiner Non Leader",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "MEMBER"
    }
    joiner_signup = await client.post("/auth/signup", json=joiner_payload)
    joiner_token = joiner_signup.json()["access_token"]
    join = await client.post(f"/groups/{group_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})
    membership_id = join.json()["id"]

    outsider_payload = {
        "email": "outsider.handle@knit.edu.in",
        "full_name": "Outsider Handle",
        "password": "Outsider@123",
        "confirm_password": "Outsider@123",
        "role": "MEMBER"
    }
    outsider_signup = await client.post("/auth/signup", json=outsider_payload)
    outsider_token = outsider_signup.json()["access_token"]

    action_payload = {"action": "APPROVED"}
    response = await client.patch(
        f"/groups/{group_id}/requests/{membership_id}",
        json=action_payload,
        headers={"Authorization": f"Bearer {outsider_token}"}
    )
    assert response.status_code == 403
    body = response.json()
    assert body["message"] == "Only the group leader can perform this action"


@pytest.mark.asyncio
async def test_handle_already_handled_request_fails(client, member_token):
    """Confirm that acting on a membership request that is no longer PENDING is rejected"""
    group_payload = {
        "name": "Already Handled Group",
        "description": "A group used to test rejecting an already-handled request",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=group_payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]

    joiner_payload = {
        "email": "joiner.alreadyhandled@knit.edu.in",
        "full_name": "Joiner Already Handled",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "MEMBER"
    }
    joiner_signup = await client.post("/auth/signup", json=joiner_payload)
    joiner_token = joiner_signup.json()["access_token"]
    join = await client.post(f"/groups/{group_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})
    membership_id = join.json()["id"]

    action_payload = {"action": "APPROVED"}
    await client.patch(
        f"/groups/{group_id}/requests/{membership_id}",
        json=action_payload,
        headers={"Authorization": f"Bearer {member_token}"}
    )
    response = await client.patch(
        f"/groups/{group_id}/requests/{membership_id}",
        json=action_payload,
        headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 403
    body = response.json()
    assert body["message"] == "Request has already been handled"


@pytest.mark.asyncio
async def test_handle_request_from_different_group_fails(client, member_token):
    """Verify that acting on a membership belonging to a different group_id than specified in the URL is rejected"""
    first_group_payload = {
        "name": "First Handle Group",
        "description": "The group the join request actually belongs to",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    first_create = await client.post(
        "/groups", json=first_group_payload, headers={"Authorization": f"Bearer {member_token}"}
    )
    first_group_id = first_create.json()["id"]

    second_group_payload = {
        "name": "Second Handle Group",
        "description": "A different group used as the wrong group_id in the URL",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    second_create = await client.post(
        "/groups", json=second_group_payload, headers={"Authorization": f"Bearer {member_token}"}
    )
    second_group_id = second_create.json()["id"]

    joiner_payload = {
        "email": "joiner.wronggroup@knit.edu.in",
        "full_name": "Joiner Wrong Group",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "MEMBER"
    }
    joiner_signup = await client.post("/auth/signup", json=joiner_payload)
    joiner_token = joiner_signup.json()["access_token"]
    join = await client.post(f"/groups/{first_group_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})
    membership_id = join.json()["id"]

    action_payload = {"action": "APPROVED"}
    response = await client.patch(
        f"/groups/{second_group_id}/requests/{membership_id}",
        json=action_payload,
        headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Membership request not found"


@pytest.mark.asyncio
async def test_handle_nonexistent_request_returns_404(client, member_token):
    """Verify that handling a nonexistent membership id returns not found"""
    group_payload = {
        "name": "Nonexistent Request Group",
        "description": "A group used to test handling a nonexistent membership request",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=group_payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]

    action_payload = {"action": "APPROVED"}
    response = await client.patch(
        f"/groups/{group_id}/requests/999999",
        json=action_payload,
        headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Membership request not found"


@pytest.mark.asyncio
async def test_handle_request_invalid_action_value_fails(client, member_token):
    """Validate that handling a join request is rejected when the action value is not a recognized enum"""
    group_payload = {
        "name": "Invalid Action Group",
        "description": "A group used to test rejection of an invalid action value",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=group_payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]

    joiner_payload = {
        "email": "joiner.invalidaction@knit.edu.in",
        "full_name": "Joiner Invalid Action",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "MEMBER"
    }
    joiner_signup = await client.post("/auth/signup", json=joiner_payload)
    joiner_token = joiner_signup.json()["access_token"]
    join = await client.post(f"/groups/{group_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})
    membership_id = join.json()["id"]

    action_payload = {"action": "MAYBE"}
    response = await client.patch(
        f"/groups/{group_id}/requests/{membership_id}",
        json=action_payload,
        headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_handle_request_without_token_fails(client, member_token):
    """Verify that handling a join request is rejected when no authentication token is provided"""
    group_payload = {
        "name": "No Token Handle Group",
        "description": "A group used to test unauthenticated handle request access",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=group_payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]

    joiner_payload = {
        "email": "joiner.notoken@knit.edu.in",
        "full_name": "Joiner No Token",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "MEMBER"
    }
    joiner_signup = await client.post("/auth/signup", json=joiner_payload)
    joiner_token = joiner_signup.json()["access_token"]
    join = await client.post(f"/groups/{group_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})
    membership_id = join.json()["id"]

    action_payload = {"action": "APPROVED"}
    response = await client.patch(f"/groups/{group_id}/requests/{membership_id}", json=action_payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# ==== members ====

@pytest.mark.asyncio
async def test_view_group_members_success(client, member_token):
    """Verify that group members can be listed, showing only approved memberships"""
    group_payload = {
        "name": "Members List Group",
        "description": "A group used to test listing approved members",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=group_payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]

    joiner_payload = {
        "email": "joiner.memberslist@knit.edu.in",
        "full_name": "Joiner Members List",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "MEMBER"
    }
    joiner_signup = await client.post("/auth/signup", json=joiner_payload)
    joiner_token = joiner_signup.json()["access_token"]
    join = await client.post(f"/groups/{group_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})
    membership_id = join.json()["id"]

    action_payload = {"action": "APPROVED"}
    await client.patch(
        f"/groups/{group_id}/requests/{membership_id}",
        json=action_payload,
        headers={"Authorization": f"Bearer {member_token}"}
    )

    response = await client.get(f"/groups/{group_id}/members", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    names = [member["full_name"] for member in response.json()]
    assert "Joiner Members List" in names


@pytest.mark.asyncio
async def test_members_list_excludes_pending_and_rejected(client, member_token):
    """Confirm that the members list only includes APPROVED memberships, excluding PENDING or REJECTED ones"""
    group_payload = {
        "name": "Members Exclusion Group",
        "description": "A group used to test that pending and rejected memberships are excluded",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=group_payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]

    pending_payload = {
        "email": "joiner.stillpending@knit.edu.in",
        "full_name": "Joiner Still Pending",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "MEMBER"
    }
    pending_signup = await client.post("/auth/signup", json=pending_payload)
    pending_token = pending_signup.json()["access_token"]
    await client.post(f"/groups/{group_id}/join", headers={"Authorization": f"Bearer {pending_token}"})

    rejected_payload = {
        "email": "joiner.gotrejected@knit.edu.in",
        "full_name": "Joiner Got Rejected",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "MEMBER"
    }
    rejected_signup = await client.post("/auth/signup", json=rejected_payload)
    rejected_token = rejected_signup.json()["access_token"]
    rejected_join = await client.post(f"/groups/{group_id}/join", headers={"Authorization": f"Bearer {rejected_token}"})
    rejected_membership_id = rejected_join.json()["id"]
    await client.patch(
        f"/groups/{group_id}/requests/{rejected_membership_id}",
        json={"action": "REJECTED"},
        headers={"Authorization": f"Bearer {member_token}"}
    )

    response = await client.get(f"/groups/{group_id}/members", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    names = [member["full_name"] for member in response.json()]
    assert "Joiner Still Pending" not in names
    assert "Joiner Got Rejected" not in names


@pytest.mark.asyncio
async def test_members_list_includes_leader(client, member_token):
    """Verify that the group leader appears in the members list as an approved member"""
    group_payload = {
        "name": "Leader Members Group",
        "description": "A group used to test that the leader appears in the members list",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=group_payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]

    response = await client.get(f"/groups/{group_id}/members", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    roles = [member["role"] for member in response.json()]
    assert "LEADER" in roles


@pytest.mark.asyncio
async def test_members_list_for_nonexistent_group_returns_404(client, member_token):
    """Verify that listing members for a nonexistent group returns not found"""
    response = await client.get("/groups/999999/members", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Group not found"


@pytest.mark.asyncio
async def test_members_without_token_fails(client, member_token):
    """Verify that listing group members is rejected when no authentication token is provided"""
    group_payload = {
        "name": "No Token Members Group",
        "description": "A group used to test unauthenticated members access",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=group_payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]

    response = await client.get(f"/groups/{group_id}/members")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"