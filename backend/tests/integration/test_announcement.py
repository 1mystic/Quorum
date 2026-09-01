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


# ==== post announcement ====

@pytest.mark.asyncio
async def test_post_announcement_success(client, leader):
    """Verify that a group leader can post an announcement to their active group"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Lab equipment rules",
        "body": "Book slots in the register before use",
        "category": "RESOURCE",
    }
    response = await client.post("/announcements", headers=headers, json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["group_id"] == group_id
    assert body["title"] == "Lab equipment rules"
    assert body["category"] == "RESOURCE"
    assert body["is_pinned"] is False
    assert body["status"] == "DRAFT"
    assert body["message"] == "Announcement created as a draft"


@pytest.mark.asyncio
async def test_post_announcement_is_pinned_explicit_true(client, leader):
    """Confirm that is_pinned can be set to true at creation time"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Urgent maintenance notice",
        "body": "The lab will be closed this weekend for maintenance",
        "category": "URGENT",
        "is_pinned": True,
    }
    response = await client.post("/announcements", headers=headers, json=payload)
    assert response.status_code == 200
    assert response.json()["is_pinned"] is True


@pytest.mark.asyncio
async def test_post_announcement_title_min_length_boundary_succeeds(client, leader):
    """Validate that posting succeeds when the title is exactly at the 3-character minimum"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Abc",
        "body": "A short title at the minimum boundary",
        "category": "GENERAL",
    }
    response = await client.post("/announcements", headers=headers, json=payload)
    assert response.status_code == 200
    assert response.json()["title"] == "Abc"


@pytest.mark.asyncio
async def test_post_announcement_title_below_min_length_fails(client, leader):
    """Validate that posting is rejected when the title is below the 3-character minimum"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Ab",
        "body": "A title that is one character too short",
        "category": "GENERAL",
    }
    response = await client.post("/announcements", headers=headers, json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_announcement_title_max_length_boundary_succeeds(client, leader):
    """Validate that posting succeeds when the title is exactly at the 150-character limit"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "A" * 150,
        "body": "A title exactly at the maximum length boundary",
        "category": "GENERAL",
    }
    response = await client.post("/announcements", headers=headers, json=payload)
    assert response.status_code == 200
    assert response.json()["title"] == "A" * 150


@pytest.mark.asyncio
async def test_post_announcement_title_over_max_length_fails(client, leader):
    """Validate that posting is rejected when the title exceeds the 150-character limit"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "A" * 151,
        "body": "A title exceeding the maximum length boundary",
        "category": "GENERAL",
    }
    response = await client.post("/announcements", headers=headers, json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_announcement_body_min_length_boundary_succeeds(client, leader):
    """Validate that posting succeeds when the body is exactly at the 5-character minimum"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Short body test",
        "body": "Hello",
        "category": "GENERAL",
    }
    response = await client.post("/announcements", headers=headers, json=payload)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_post_announcement_body_below_min_length_fails(client, leader):
    """Validate that posting is rejected when the body is below the 5-character minimum"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Too short body test",
        "body": "Hi",
        "category": "GENERAL",
    }
    response = await client.post("/announcements", headers=headers, json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_announcement_body_over_max_length_fails(client, leader):
    """Validate that posting is rejected when the body exceeds the 5000-character limit"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Too long body test",
        "body": "A" * 5001,
        "category": "GENERAL",
    }
    response = await client.post("/announcements", headers=headers, json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_announcement_invalid_category_fails(client, leader):
    """Validate that posting is rejected when the category is not a recognized enum value"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Bad category test",
        "body": "This announcement has an invalid category value",
        "category": "SPAM",
    }
    response = await client.post("/announcements", headers=headers, json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_announcement_missing_fields_fails(client, leader):
    """Validate that posting is rejected when required fields are missing"""
    headers, group_id = leader
    payload = {"group_id": group_id}
    response = await client.post("/announcements", headers=headers, json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_post_announcement_unknown_group_fails(client, leader):
    """Confirm that posting is rejected when the group does not exist"""
    headers, _ = leader
    payload = {
        "group_id": 999999,
        "title": "Ghost group announcement",
        "body": "This group does not exist at all",
        "category": "GENERAL",
    }
    response = await client.post("/announcements", headers=headers, json=payload)
    assert response.status_code == 404
    assert response.json()["message"] == "Group not found"


@pytest.mark.asyncio
async def test_post_announcement_cross_tenant_group_fails(client, leader):
    """Confirm that posting is rejected when the group belongs to a different tenant"""
    other_admin_payload = {
        "email": "admin@otherannounce.edu.in",
        "full_name": "Other Announce Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "TENANT_ADMIN",
    }
    other_admin_signup = await client.post("/auth/signup", json=other_admin_payload)
    other_admin_token = other_admin_signup.json()["access_token"]

    tenant_payload = {
        "name": "Other Announce Tenant",
        "slug": "announceme-other-announce-tenant",
        "vertical": "campus_club",
        "description": "A separate tenant for announcement scoping tests",
    }
    await client.post(
        "/tenant/onboarding", json=tenant_payload,
        headers={"Authorization": f"Bearer {other_admin_token}"},
    )

    other_member_payload = {
        "email": "leader@otherannounce.edu.in",
        "full_name": "Other Announce Leader",
        "password": "Leader@123",
        "confirm_password": "Leader@123",
        "role": "MEMBER",
        "tenant_slug": "announceme-other-announce-tenant",
    }
    other_member_signup = await client.post("/auth/signup", json=other_member_payload)
    other_headers = {"Authorization": f"Bearer {other_member_signup.json()['access_token']}"}

    group_payload = {
        "name": "Foreign Tenant Group",
        "description": "A group that belongs to a different tenant",
        "category": "Technical",
        "type": "UNOFFICIAL",
    }
    other_group = await client.post("/groups", headers=other_headers, json=group_payload)
    other_group_id = other_group.json()["id"]

    headers, _ = leader
    payload = {
        "group_id": other_group_id,
        "title": "Cross tenant attempt",
        "body": "Trying to post into a group from another tenant",
        "category": "GENERAL",
    }
    response = await client.post("/announcements", headers=headers, json=payload)
    assert response.status_code == 404
    assert response.json()["message"] == "Group not found"


@pytest.mark.asyncio
async def test_post_announcement_pending_group_fails(client,seed_tenant):
    """Confirm that posting is rejected when the group is still PENDING approval"""
    payload = {
        "email": "pendingleader@knit.edu.in",
        "full_name": "Pending Leader",
        "password": "Test@1234",
        "confirm_password": "Test@1234",
        "role": "MEMBER",
        "tenant_slug": seed_tenant.slug,
    }
    signup = await client.post("/auth/signup", json=payload)
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    group_payload = {
        "name": "Pending Announce Group",
        "description": "A group left pending for announcement testing",
        "category": "Technical",
        "type": "OFFICIAL",
    }
    group = await client.post("/groups", headers=headers, json=group_payload)
    group_id = group.json()["id"]

    payload = {
        "group_id": group_id,
        "title": "Announcement in pending group",
        "body": "This group is not active yet",
        "category": "GENERAL",
    }
    response = await client.post("/announcements", headers=headers, json=payload)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_post_announcement_by_non_leader_fails(client, leader, member):
    """Ensure that a plain group member cannot post an announcement"""
    _, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Unauthorised announcement",
        "body": "This should never be posted by a member",
        "category": "GENERAL",
    }
    response = await client.post("/announcements", headers=member, json=payload)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_post_announcement_without_token_fails(client, leader):
    """Ensure that posting is rejected when no access token is supplied"""
    _, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Anonymous announcement",
        "body": "Posted without any authentication",
        "category": "GENERAL",
    }
    response = await client.post("/announcements", json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# ==== submit / approve / reject ====

@pytest.mark.asyncio
async def test_submit_announcement_for_review_success(client, leader):
    """Verify that a leader can submit a draft announcement for admin review"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Draft to submit",
        "body": "This announcement is about to be submitted for review",
        "category": "GENERAL",
    }
    posted = await client.post("/announcements", headers=headers, json=payload)
    announcement_id = posted.json()["id"]

    response = await client.patch(f"/announcements/{announcement_id}/submit-for-review", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "SUBMITTED"


@pytest.mark.asyncio
async def test_draft_announcement_hidden_from_member_feed(client, leader, member):
    """Confirm that a draft, never submitted or approved, never reaches the member feed"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Still a draft",
        "body": "This announcement has never been submitted for review",
        "category": "GENERAL",
    }
    posted = await client.post("/announcements", headers=headers, json=payload)
    announcement_id = posted.json()["id"]

    response = await client.get("/announcements", headers=member)
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert announcement_id not in ids


@pytest.mark.asyncio
async def test_submitted_announcement_still_hidden_until_approved(client, leader, member):
    """Confirm that a submitted-but-not-yet-approved announcement stays out of the member feed"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Awaiting review",
        "body": "This announcement has been submitted but not approved",
        "category": "GENERAL",
    }
    posted = await client.post("/announcements", headers=headers, json=payload)
    announcement_id = posted.json()["id"]
    await client.patch(f"/announcements/{announcement_id}/submit-for-review", headers=headers)

    response = await client.get("/announcements", headers=member)
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert announcement_id not in ids


@pytest.mark.asyncio
async def test_approve_announcement_success(client, leader, member, tenant_admin):
    """Verify that a tenant admin can approve a submitted announcement, making it visible to members"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Ready for approval",
        "body": "This announcement is ready for a tenant admin to approve",
        "category": "GENERAL",
    }
    posted = await client.post("/announcements", headers=headers, json=payload)
    announcement_id = posted.json()["id"]
    await client.patch(f"/announcements/{announcement_id}/submit-for-review", headers=headers)

    response = await client.patch(f"/announcements/{announcement_id}/approve", headers=tenant_admin)
    assert response.status_code == 200
    assert response.json()["status"] == "PUBLISHED"

    feed = await client.get("/announcements", headers=member)
    ids = [item["id"] for item in feed.json()]
    assert announcement_id in ids


@pytest.mark.asyncio
async def test_approve_draft_announcement_fails(client, leader, tenant_admin):
    """Confirm that a draft announcement cannot be approved before it is submitted"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Not yet submitted",
        "body": "This announcement was never submitted for review",
        "category": "GENERAL",
    }
    posted = await client.post("/announcements", headers=headers, json=payload)
    announcement_id = posted.json()["id"]

    response = await client.patch(f"/announcements/{announcement_id}/approve", headers=tenant_admin)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_approve_announcement_by_non_admin_fails(client, leader):
    """Ensure that a group leader cannot approve their own submission"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Self approval attempt",
        "body": "A leader should not be able to approve their own announcement",
        "category": "GENERAL",
    }
    posted = await client.post("/announcements", headers=headers, json=payload)
    announcement_id = posted.json()["id"]
    await client.patch(f"/announcements/{announcement_id}/submit-for-review", headers=headers)

    response = await client.patch(f"/announcements/{announcement_id}/approve", headers=headers)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_reject_announcement_success_and_resubmit(client, leader, member, tenant_admin):
    """A rejection carries a reason and returns the announcement to a resubmittable state"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Needs rework",
        "body": "This announcement will be rejected and then revised",
        "category": "GENERAL",
    }
    posted = await client.post("/announcements", headers=headers, json=payload)
    announcement_id = posted.json()["id"]
    await client.patch(f"/announcements/{announcement_id}/submit-for-review", headers=headers)

    response = await client.patch(
        f"/announcements/{announcement_id}/reject", headers=tenant_admin,
        json={"reason": "Please cite the source of this claim"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "REJECTED"
    assert response.json()["rejection_reason"] == "Please cite the source of this claim"

    feed = await client.get("/announcements", headers=member)
    assert announcement_id not in [item["id"] for item in feed.json()]

    resubmit = await client.patch(f"/announcements/{announcement_id}/submit-for-review", headers=headers)
    assert resubmit.status_code == 200
    assert resubmit.json()["status"] == "SUBMITTED"

    approve = await client.patch(f"/announcements/{announcement_id}/approve", headers=tenant_admin)
    assert approve.status_code == 200
    assert approve.json()["status"] == "PUBLISHED"


@pytest.mark.asyncio
async def test_reject_announcement_not_submitted_fails(client, leader, tenant_admin):
    """Confirm that a draft announcement cannot be rejected before it is submitted"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Not yet submitted",
        "body": "This announcement was never submitted for review",
        "category": "GENERAL",
    }
    posted = await client.post("/announcements", headers=headers, json=payload)
    announcement_id = posted.json()["id"]

    response = await client.patch(
        f"/announcements/{announcement_id}/reject", headers=tenant_admin, json={"reason": "Too early"}
    )
    assert response.status_code == 403


# ==== feed ====

@pytest.mark.asyncio
async def test_feed_returns_approved_member_announcements(client, leader, member, tenant_admin):
    """Verify that an approved member sees announcements from their joined group in the feed"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Feed visibility test",
        "body": "This should show up in the member's feed",
        "category": "GENERAL",
    }
    posted = await client.post("/announcements", headers=headers, json=payload)
    announcement_id = posted.json()["id"]
    await client.patch(f"/announcements/{announcement_id}/submit-for-review", headers=headers)
    await client.patch(f"/announcements/{announcement_id}/approve", headers=tenant_admin)

    response = await client.get("/announcements", headers=member)
    assert response.status_code == 200
    body = response.json()
    ids = [item["id"] for item in body]
    assert announcement_id in ids
    item = next(i for i in body if i["id"] == announcement_id)
    assert item["group_id"] == group_id
    assert item["group_name"] == "Robotics Group"
    assert item["author_name"] == "Group Leader"
    assert item["unread"] is True


@pytest.mark.asyncio
async def test_feed_hides_announcements_for_pending_membership(client, leader, outsider):
    """Confirm that a member with a pending join request sees no announcements from that group"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Hidden from pending member",
        "body": "A pending member should not see this announcement",
        "category": "GENERAL",
    }
    posted = await client.post("/announcements", headers=headers, json=payload)
    announcement_id = posted.json()["id"]

    await client.post(f"/groups/{group_id}/join", headers=outsider)

    response = await client.get("/announcements", headers=outsider)
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert announcement_id not in ids


@pytest.mark.asyncio
async def test_feed_empty_for_member_with_no_groups(client, outsider):
    """Confirm that a member with no group memberships gets an empty feed"""
    response = await client.get("/announcements", headers=outsider)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_feed_pinned_announcements_appear_first(client, leader, member, tenant_admin):
    """Verify that pinned announcements are ordered before unpinned ones in the feed"""
    headers, group_id = leader
    unpinned_payload = {
        "group_id": group_id,
        "title": "Regular update",
        "body": "A normal, unpinned announcement",
        "category": "GENERAL",
    }
    unpinned = await client.post("/announcements", headers=headers, json=unpinned_payload)
    unpinned_id = unpinned.json()["id"]
    await client.patch(f"/announcements/{unpinned_id}/submit-for-review", headers=headers)
    await client.patch(f"/announcements/{unpinned_id}/approve", headers=tenant_admin)

    pinned_payload = {
        "group_id": group_id,
        "title": "Important pinned notice",
        "body": "This announcement is pinned to the top",
        "category": "URGENT",
        "is_pinned": True,
    }
    pinned = await client.post("/announcements", headers=headers, json=pinned_payload)
    pinned_id = pinned.json()["id"]
    await client.patch(f"/announcements/{pinned_id}/submit-for-review", headers=headers)
    await client.patch(f"/announcements/{pinned_id}/approve", headers=tenant_admin)

    response = await client.get("/announcements", headers=member)
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert ids.index(pinned_id) < ids.index(unpinned_id)


@pytest.mark.asyncio
async def test_feed_filter_by_group_id(client, leader, member, tenant_admin):
    """Verify that filtering the feed by group_id returns only that group's announcements"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Group scoped announcement",
        "body": "This announcement belongs to a specific group",
        "category": "GENERAL",
    }
    posted = await client.post("/announcements", headers=headers, json=payload)
    announcement_id = posted.json()["id"]
    await client.patch(f"/announcements/{announcement_id}/submit-for-review", headers=headers)
    await client.patch(f"/announcements/{announcement_id}/approve", headers=tenant_admin)

    response = await client.get("/announcements", headers=member, params={"group_id": group_id})
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert announcement_id in ids


@pytest.mark.asyncio
async def test_feed_filter_by_category(client, leader, member, tenant_admin):
    """Verify that filtering the feed by category returns only matching announcements"""
    headers, group_id = leader
    resource_payload = {
        "group_id": group_id,
        "title": "Resource announcement",
        "body": "An announcement in the resource category",
        "category": "RESOURCE",
    }
    resource = await client.post("/announcements", headers=headers, json=resource_payload)
    resource_id = resource.json()["id"]
    await client.patch(f"/announcements/{resource_id}/submit-for-review", headers=headers)
    await client.patch(f"/announcements/{resource_id}/approve", headers=tenant_admin)

    general_payload = {
        "group_id": group_id,
        "title": "General announcement",
        "body": "An announcement in the general category",
        "category": "GENERAL",
    }
    general = await client.post("/announcements", headers=headers, json=general_payload)
    general_id = general.json()["id"]
    await client.patch(f"/announcements/{general_id}/submit-for-review", headers=headers)
    await client.patch(f"/announcements/{general_id}/approve", headers=tenant_admin)

    response = await client.get("/announcements", headers=member, params={"category": "RESOURCE"})
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert resource_id in ids
    assert general_id not in ids


@pytest.mark.asyncio
async def test_feed_search_matches_title(client, leader, member, tenant_admin):
    """Verify that the search filter matches an announcement by its title"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Lab equipment rules",
        "body": "Book slots in the register before use",
        "category": "RESOURCE",
    }
    posted = await client.post("/announcements", headers=headers, json=payload)
    announcement_id = posted.json()["id"]
    await client.patch(f"/announcements/{announcement_id}/submit-for-review", headers=headers)
    await client.patch(f"/announcements/{announcement_id}/approve", headers=tenant_admin)

    response = await client.get("/announcements", headers=member, params={"search": "equipment"})
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert announcement_id in ids


@pytest.mark.asyncio
async def test_feed_search_matches_body(client, leader, member, tenant_admin):
    """Verify that the search filter matches an announcement by its body text"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Weekend session",
        "body": "Please bring your own soldering iron",
        "category": "GENERAL",
    }
    posted = await client.post("/announcements", headers=headers, json=payload)
    announcement_id = posted.json()["id"]
    await client.patch(f"/announcements/{announcement_id}/submit-for-review", headers=headers)
    await client.patch(f"/announcements/{announcement_id}/approve", headers=tenant_admin)

    response = await client.get("/announcements", headers=member, params={"search": "soldering"})
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert announcement_id in ids


@pytest.mark.asyncio
async def test_feed_search_no_match_returns_empty(client, leader, member):
    """Confirm that the search filter returns an empty list when nothing matches"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Lab equipment rules",
        "body": "Book slots in the register before use",
        "category": "RESOURCE",
    }
    await client.post("/announcements", headers=headers, json=payload)

    response = await client.get("/announcements", headers=member, params={"search": "zumba"})
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_feed_search_below_min_length_fails(client, member):
    """Validate that the feed is rejected when the search query is empty"""
    response = await client.get("/announcements", headers=member, params={"search": ""})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_feed_without_token_fails(client):
    """Ensure that requesting the feed is rejected without an access token"""
    response = await client.get("/announcements")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# ==== mine ====

@pytest.mark.asyncio
async def test_mine_returns_leader_group_announcements(client, leader):
    """Verify that a leader's own noticeboard returns announcements from groups they lead"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Leader noticeboard test",
        "body": "This should appear on the leader's own noticeboard",
        "category": "GENERAL",
    }
    posted = await client.post("/announcements", headers=headers, json=payload)
    announcement_id = posted.json()["id"]

    response = await client.get("/announcements/mine", headers=headers)
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert announcement_id in ids


@pytest.mark.asyncio
async def test_mine_empty_for_non_leader_member(client, leader, member):
    """Confirm that a plain member with no led groups gets an empty list from /mine"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Not visible to member's mine view",
        "body": "This group is led by someone else, not the member",
        "category": "GENERAL",
    }
    await client.post("/announcements", headers=headers, json=payload)

    response = await client.get("/announcements/mine", headers=member)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_mine_without_token_fails(client):
    """Ensure that requesting /mine is rejected without an access token"""
    response = await client.get("/announcements/mine")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# ==== unread count ====

@pytest.mark.asyncio
async def test_unread_count_reflects_new_announcement(client, leader, member, tenant_admin):
    """Verify that unread-count increases after a new announcement is posted"""
    headers, group_id = leader
    before = await client.get("/announcements/unread-count", headers=member)
    assert before.status_code == 200
    initial_count = before.json()["count"]

    payload = {
        "group_id": group_id,
        "title": "Unread count test",
        "body": "This announcement should increase the unread count",
        "category": "GENERAL",
    }
    posted = await client.post("/announcements", headers=headers, json=payload)
    announcement_id = posted.json()["id"]
    await client.patch(f"/announcements/{announcement_id}/submit-for-review", headers=headers)
    await client.patch(f"/announcements/{announcement_id}/approve", headers=tenant_admin)

    after = await client.get("/announcements/unread-count", headers=member)
    assert after.status_code == 200
    assert after.json()["count"] == initial_count + 1


@pytest.mark.asyncio
async def test_unread_count_zero_for_member_with_no_groups(client, outsider):
    """Confirm that a member with no groups has an unread count of zero"""
    response = await client.get("/announcements/unread-count", headers=outsider)
    assert response.status_code == 200
    assert response.json()["count"] == 0


# ==== read-all ====

@pytest.mark.asyncio
async def test_mark_read_all_success(client, leader, member):
    """Verify that marking all announcements read zeroes the unread count and clears unread flags"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Mark read test",
        "body": "This announcement will be marked as read",
        "category": "GENERAL",
    }
    await client.post("/announcements", headers=headers, json=payload)

    response = await client.post("/announcements/read-all", headers=member)
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "All announcements marked as read"
    assert "seen_at" in body

    count = await client.get("/announcements/unread-count", headers=member)
    assert count.json()["count"] == 0

    feed = await client.get("/announcements", headers=member)
    assert all(item["unread"] is False for item in feed.json())


@pytest.mark.asyncio
async def test_new_announcement_after_read_all_is_unread_again(client, db_session, leader, member, tenant_admin):
    """Confirm that an announcement posted after read-all is marked unread"""
    from datetime import datetime, timedelta, timezone
    from app.models import Announcement

    headers, group_id = leader
    first_payload = {
        "group_id": group_id,
        "title": "Read before this one",
        "body": "This announcement is read before the next is posted",
        "category": "GENERAL",
    }
    await client.post("/announcements", headers=headers, json=first_payload)
    await client.post("/announcements/read-all", headers=member)

    second_payload = {
        "group_id": group_id,
        "title": "Posted after read-all",
        "body": "This announcement should be unread again",
        "category": "GENERAL",
    }
    posted = await client.post("/announcements", headers=headers, json=second_payload)
    announcement_id = posted.json()["id"]
    await client.patch(f"/announcements/{announcement_id}/submit-for-review", headers=headers)
    await client.patch(f"/announcements/{announcement_id}/approve", headers=tenant_admin)

    announcement = await db_session.get(Announcement, announcement_id)
    announcement.created_at = datetime.now(timezone.utc) + timedelta(seconds=5)
    await db_session.flush()

    feed = await client.get("/announcements", headers=member)
    item = next((i for i in feed.json() if i["id"] == announcement_id), None)
    assert item is not None
    assert item["unread"] is True


# ==== pin / unpin ====

@pytest.mark.asyncio
async def test_pin_announcement_success(client, leader):
    """Verify that a leader can pin an announcement"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Pin me",
        "body": "This announcement will be pinned",
        "category": "GENERAL",
    }
    posted = await client.post("/announcements", headers=headers, json=payload)
    announcement_id = posted.json()["id"]

    response = await client.patch(
        f"/announcements/{announcement_id}/pin", headers=headers, json={"pinned": True}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == announcement_id
    assert body["is_pinned"] is True
    assert body["message"] == "Announcement pinned to the top of the feed"


@pytest.mark.asyncio
async def test_unpin_announcement_success(client, leader):
    """Verify that a leader can unpin a previously pinned announcement"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Unpin me",
        "body": "This announcement will be pinned then unpinned",
        "category": "GENERAL",
        "is_pinned": True,
    }
    posted = await client.post("/announcements", headers=headers, json=payload)
    announcement_id = posted.json()["id"]

    response = await client.patch(
        f"/announcements/{announcement_id}/pin", headers=headers, json={"pinned": False}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_pinned"] is False
    assert body["message"] == "Announcement unpinned"


@pytest.mark.asyncio
async def test_pin_unknown_announcement_fails(client, leader):
    """Confirm that pinning a nonexistent announcement returns not found"""
    headers, _ = leader
    response = await client.patch(
        "/announcements/999999/pin", headers=headers, json={"pinned": True}
    )
    assert response.status_code == 404
    assert response.json()["message"] == "Announcement not found"


@pytest.mark.asyncio
async def test_pin_by_non_leader_fails(client, leader, member):
    """Ensure that a plain group member cannot pin an announcement"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Not pinnable by member",
        "body": "A member should not be able to pin this",
        "category": "GENERAL",
    }
    posted = await client.post("/announcements", headers=headers, json=payload)
    announcement_id = posted.json()["id"]

    response = await client.patch(
        f"/announcements/{announcement_id}/pin", headers=member, json={"pinned": True}
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_pin_missing_field_fails(client, leader):
    """Validate that pinning is rejected when the pinned field is missing"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Missing pinned field",
        "body": "This request omits the required pinned field",
        "category": "GENERAL",
    }
    posted = await client.post("/announcements", headers=headers, json=payload)
    announcement_id = posted.json()["id"]

    response = await client.patch(f"/announcements/{announcement_id}/pin", headers=headers, json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_pin_without_token_fails(client, leader):
    """Ensure that pinning is rejected without an access token"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "No token pin attempt",
        "body": "Trying to pin without authentication",
        "category": "GENERAL",
    }
    posted = await client.post("/announcements", headers=headers, json=payload)
    announcement_id = posted.json()["id"]

    response = await client.patch(f"/announcements/{announcement_id}/pin", json={"pinned": True})
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# ==== delete ====

@pytest.mark.asyncio
async def test_delete_announcement_success(client, leader):
    """Verify that a leader can delete their group's announcement"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Delete me",
        "body": "This announcement will be deleted",
        "category": "GENERAL",
    }
    posted = await client.post("/announcements", headers=headers, json=payload)
    announcement_id = posted.json()["id"]

    response = await client.delete(f"/announcements/{announcement_id}", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == announcement_id
    assert body["message"] == "Announcement deleted successfully"

    feed = await client.get("/announcements/mine", headers=headers)
    ids = [item["id"] for item in feed.json()]
    assert announcement_id not in ids


@pytest.mark.asyncio
async def test_delete_unknown_announcement_fails(client, leader):
    """Confirm that deleting a nonexistent announcement returns not found"""
    headers, _ = leader
    response = await client.delete("/announcements/999999", headers=headers)
    assert response.status_code == 404
    assert response.json()["message"] == "Announcement not found"


@pytest.mark.asyncio
async def test_delete_by_non_leader_fails(client, leader, member):
    """Ensure that a plain group member cannot delete an announcement"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Not deletable by member",
        "body": "A member should not be able to delete this",
        "category": "GENERAL",
    }
    posted = await client.post("/announcements", headers=headers, json=payload)
    announcement_id = posted.json()["id"]

    response = await client.delete(f"/announcements/{announcement_id}", headers=member)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_without_token_fails(client, leader):
    """Ensure that deleting is rejected without an access token"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "No token delete attempt",
        "body": "Trying to delete without authentication",
        "category": "GENERAL",
    }
    posted = await client.post("/announcements", headers=headers, json=payload)
    announcement_id = posted.json()["id"]

    response = await client.delete(f"/announcements/{announcement_id}")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"

# ==== additional edge cases ====

@pytest.mark.asyncio
async def test_post_announcement_lowercase_category_fails(client, leader):
    """Validate that posting is rejected when the category uses lowercase casing"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Lowercase category test",
        "body": "This announcement uses a lowercase category value",
        "category": "general",
    }
    response = await client.post("/announcements", headers=headers, json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_feed_lowercase_category_filter_fails(client, member):
    """Validate that the feed is rejected when the category filter uses lowercase casing"""
    response = await client.get("/announcements", headers=member, params={"category": "general"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_mine_lowercase_category_filter_fails(client, leader):
    """Validate that /mine is rejected when the category filter uses lowercase casing"""
    headers, _ = leader
    response = await client.get("/announcements/mine", headers=headers, params={"category": "urgent"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_feed_limit_zero_fails(client, member):
    """Validate that the feed is rejected when limit is below the minimum of 1"""
    response = await client.get("/announcements", headers=member, params={"limit": 0})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_feed_limit_over_max_fails(client, member):
    """Validate that the feed is rejected when limit exceeds the maximum of 100"""
    response = await client.get("/announcements", headers=member, params={"limit": 101})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_feed_offset_negative_fails(client, member):
    """Validate that the feed is rejected when offset is negative"""
    response = await client.get("/announcements", headers=member, params={"offset": -1})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_feed_limit_caps_returned_items(client, leader, member, tenant_admin):
    """Confirm that limit actually caps the number of announcements returned, not just accepted"""
    headers, group_id = leader
    for i in range(3):
        payload = {
            "group_id": group_id,
            "title": f"Capped announcement {i}",
            "body": f"Announcement number {i} used to test the limit cap",
            "category": "GENERAL",
        }
        posted = await client.post("/announcements", headers=headers, json=payload)
        announcement_id = posted.json()["id"]
        await client.patch(f"/announcements/{announcement_id}/submit-for-review", headers=headers)
        await client.patch(f"/announcements/{announcement_id}/approve", headers=tenant_admin)

    response = await client.get("/announcements", headers=member, params={"limit": 1})
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_feed_group_id_for_unjoined_group_returns_empty(client, leader, member):
    """Confirm that filtering by a group_id the member is not a member of returns an empty list, not an error"""
    other_payload = {
        "email": "othergroupleader@knit.edu.in",
        "full_name": "Other Group Leader",
        "password": "Test@1234",
        "confirm_password": "Test@1234",
        "role": "MEMBER",
        "tenant_slug": "test-university",
    }
    signup = await client.post("/auth/signup", json=other_payload)
    other_headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    group_payload = {
        "name": "Unjoined Group",
        "description": "A group the member has never joined",
        "category": "Technical",
        "type": "UNOFFICIAL",
    }
    other_group = await client.post("/groups", headers=other_headers, json=group_payload)
    other_group_id = other_group.json()["id"]

    announcement_payload = {
        "group_id": other_group_id,
        "title": "Announcement in unjoined group",
        "body": "The member should never see this via group_id filter",
        "category": "GENERAL",
    }
    await client.post("/announcements", headers=other_headers, json=announcement_payload)

    response = await client.get("/announcements", headers=member, params={"group_id": other_group_id})
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_feed_unread_false_at_exact_seen_at_boundary(client, db_session, leader, member, tenant_admin):
    """Confirm that an announcement created at the exact same instant as seen_at counts as read"""
    from app.models import Announcement, Member

    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Boundary timestamp test",
        "body": "This announcement's created_at will be forced to equal seen_at exactly",
        "category": "GENERAL",
    }
    posted = await client.post("/announcements", headers=headers, json=payload)
    announcement_id = posted.json()["id"]
    await client.patch(f"/announcements/{announcement_id}/submit-for-review", headers=headers)
    await client.patch(f"/announcements/{announcement_id}/approve", headers=tenant_admin)

    await client.post("/announcements/read-all", headers=member)

    member_user_id = int(
        __import__("jose").jwt.get_unverified_claims(
            member["Authorization"].split(" ")[1]
        )["sub"]
    )
    result = await db_session.execute(
        Member.__table__.select().where(Member.user_id == member_user_id)
    )
    member_row = result.first()
    seen_at = member_row.announcements_seen_at

    announcement = await db_session.get(Announcement, announcement_id)
    announcement.created_at = seen_at
    await db_session.flush()

    feed = await client.get("/announcements", headers=member)
    item = next(i for i in feed.json() if i["id"] == announcement_id)
    assert item["unread"] is False


@pytest.mark.asyncio
async def test_feed_search_percent_wildcard_behaves_as_wildcard(client, leader, member, tenant_admin):
    """Confirm that a literal percent sign in the search term is treated as a SQL wildcard, not a literal character"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Discount notice",
        "body": "Members get 100 rupees off registration this month",
        "category": "GENERAL",
    }
    posted = await client.post("/announcements", headers=headers, json=payload)
    announcement_id = posted.json()["id"]
    await client.patch(f"/announcements/{announcement_id}/submit-for-review", headers=headers)
    await client.patch(f"/announcements/{announcement_id}/approve", headers=tenant_admin)

    response = await client.get("/announcements", headers=member, params={"search": "100%off"})
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert announcement_id in ids


@pytest.mark.asyncio
async def test_mine_combined_filters(client, leader):
    """Verify that /mine correctly applies group_id, category, and search together"""
    headers, group_id = leader
    matching_payload = {
        "group_id": group_id,
        "title": "Combined filter match",
        "body": "This should match all three combined filters",
        "category": "RESOURCE",
    }
    matching = await client.post("/announcements", headers=headers, json=matching_payload)
    matching_id = matching.json()["id"]

    non_matching_payload = {
        "group_id": group_id,
        "title": "Different category",
        "body": "This should not match the category filter",
        "category": "GENERAL",
    }
    non_matching = await client.post("/announcements", headers=headers, json=non_matching_payload)
    non_matching_id = non_matching.json()["id"]

    response = await client.get(
        "/announcements/mine",
        headers=headers,
        params={"group_id": group_id, "category": "RESOURCE", "search": "combined"},
    )
    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert matching_id in ids
    assert non_matching_id not in ids


@pytest.mark.asyncio
async def test_pin_already_pinned_announcement_succeeds_idempotently(client, leader):
    """Confirm that pinning an already-pinned announcement succeeds again without error"""
    headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Double pin test",
        "body": "This announcement will be pinned twice in a row",
        "category": "GENERAL",
        "is_pinned": True,
    }
    posted = await client.post("/announcements", headers=headers, json=payload)
    announcement_id = posted.json()["id"]

    response = await client.patch(
        f"/announcements/{announcement_id}/pin", headers=headers, json={"pinned": True}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_pinned"] is True
    assert body["message"] == "Announcement pinned to the top of the feed"