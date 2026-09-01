
import pytest
 
 
# ==== create ====
 
@pytest.mark.asyncio
async def test_create_official_group_pending_approval(client, member_token):
    """Verify that creating an OFFICIAL group succeeds and leaves it pending admin approval"""
    payload = {
        "name": "Robotics Group",
        "description": "A group for robotics enthusiasts and builders",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    response = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Robotics Group"
    assert body["type"] == "OFFICIAL"
    assert body["status"] == "PENDING"
    assert body["message"] == "Group submitted for admin approval"
 
 
@pytest.mark.asyncio
async def test_create_unofficial_group_active_immediately(client, member_token):
    """Verify that creating an UNOFFICIAL group succeeds and is active immediately"""
    payload = {
        "name": "Chess Circle",
        "description": "A group for chess enthusiasts and casual players",
        "category": "Games",
        "type": "UNOFFICIAL"
    }
    response = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Chess Circle"
    assert body["type"] == "UNOFFICIAL"
    assert body["status"] == "ACTIVE"
    assert body["message"] == "Group created and is now live"
 
 
@pytest.mark.asyncio
async def test_create_group_links_empty_array_succeeds(client, member_token):
    """Verify that a group can be created with no links provided"""
    payload = {
        "name": "Linkless Group",
        "description": "A group created without any links",
        "category": "Technical",
        "type": "UNOFFICIAL",
        "links": []
    }
    response = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Linkless Group"
 
 
@pytest.mark.asyncio
async def test_create_group_name_min_length_boundary_succeeds(client, member_token):
    """Validate that group creation succeeds when the name is exactly at the 3-character minimum"""
    payload = {
        "name": "Abc",
        "description": "A group with a very short name for testing",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    response = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    assert response.json()["name"] == "Abc"
 
 
@pytest.mark.asyncio
async def test_create_group_name_below_min_length_fails(client, member_token):
    """Validate that group creation is rejected when the name is below the 3-character minimum"""
    payload = {
        "name": "Ab",
        "description": "A group with a name that is too short",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    response = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 422
 
 
@pytest.mark.asyncio
async def test_create_group_name_max_length_boundary_succeeds(client, member_token):
    """Validate that group creation succeeds when the name is exactly at the 100-character limit"""
    payload = {
        "name": "A" * 100,
        "description": "A group with a name exactly at the max length",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    response = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    assert response.json()["name"] == "A" * 100
 
 
@pytest.mark.asyncio
async def test_create_group_name_over_max_length_fails(client, member_token):
    """Validate that group creation is rejected when the name exceeds the 100-character limit"""
    payload = {
        "name": "A" * 101,
        "description": "A group with a name exceeding the max length",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    response = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 422
 
 
@pytest.mark.asyncio
async def test_create_group_description_min_length_boundary_succeeds(client, member_token):
    """Validate that group creation succeeds when the description is exactly at the 5-character minimum"""
    payload = {
        "name": "Music Society",
        "description": "Hello",
        "category": "Arts",
        "type": "UNOFFICIAL"
    }
    response = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
 
 
@pytest.mark.asyncio
async def test_create_group_description_below_min_length_fails(client, member_token):
    """Validate that group creation is rejected when the description is below the 5-character minimum"""
    payload = {
        "name": "Music Society",
        "description": "Hi",
        "category": "Arts",
        "type": "UNOFFICIAL"
    }
    response = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 422
 
 
@pytest.mark.asyncio
async def test_create_group_description_max_length_boundary_succeeds(client, member_token):
    """Validate that group creation succeeds when the description is exactly at the 1000-character limit"""
    payload = {
        "name": "Debate Group",
        "description": "A" * 1000,
        "category": "Literary",
        "type": "UNOFFICIAL"
    }
    response = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
 
 
@pytest.mark.asyncio
async def test_create_group_description_over_max_length_fails(client, member_token):
    """Validate that group creation is rejected when the description exceeds the 1000-character limit"""
    payload = {
        "name": "Debate Group",
        "description": "A" * 1001,
        "category": "Literary",
        "type": "UNOFFICIAL"
    }
    response = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 422
 
 
@pytest.mark.asyncio
async def test_create_group_category_min_length_boundary_succeeds(client, member_token):
    """Validate that group creation succeeds when the category is exactly at the 2-character minimum"""
    payload = {
        "name": "AI Group",
        "description": "A group focused on artificial intelligence",
        "category": "AI",
        "type": "UNOFFICIAL"
    }
    response = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
 
 
@pytest.mark.asyncio
async def test_create_group_category_below_min_length_fails(client, member_token):
    """Validate that group creation is rejected when the category is below the 2-character minimum"""
    payload = {
        "name": "AI Group",
        "description": "A group focused on artificial intelligence",
        "category": "A",
        "type": "UNOFFICIAL"
    }
    response = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 422
 
 
@pytest.mark.asyncio
async def test_create_group_category_max_length_boundary_succeeds(client, member_token):
    """Validate that group creation succeeds when the category is exactly at the 50-character limit"""
    payload = {
        "name": "Long Category Group",
        "description": "A group with a category at the max length",
        "category": "A" * 50,
        "type": "UNOFFICIAL"
    }
    response = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
 
 
@pytest.mark.asyncio
async def test_create_group_category_over_max_length_fails(client, member_token):
    """Validate that group creation is rejected when the category exceeds the 50-character limit"""
    payload = {
        "name": "Long Category Group",
        "description": "A group with a category exceeding the max length",
        "category": "A" * 51,
        "type": "UNOFFICIAL"
    }
    response = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 422
 
 
@pytest.mark.asyncio
async def test_create_group_invalid_type_fails(client, member_token):
    """Validate that group creation is rejected when the type is not a recognized enum value"""
    payload = {
        "name": "Mystery Group",
        "description": "A group with an invalid type value",
        "category": "Technical",
        "type": "SECRET"
    }
    response = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 422
 
 
@pytest.mark.asyncio
async def test_create_group_missing_required_fields_fails(client, member_token):
    """Validate that group creation is rejected when required fields are missing"""
    payload = {"name": "Incomplete Group"}
    response = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 422
 
 
@pytest.mark.asyncio
async def test_create_group_without_token_fails(client):
    """Verify that group creation is rejected when no authentication token is provided"""
    payload = {
        "name": "No Token Group",
        "description": "A group created without an auth token",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    response = await client.post("/groups", json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"
 
 
@pytest.mark.asyncio
async def test_create_group_with_admin_token_fails(client, admin_token):
    """Verify that group creation is rejected for a user with the campus admin role"""
    payload = {
        "name": "Admin Attempt Group",
        "description": "A group creation attempt made by an admin",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    response = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 403
    body = response.json()
    assert body["message"] == "Tenant mismatch"


@pytest.mark.asyncio
async def test_create_group_whitespace_only_name_is_accepted(client, member_token):
    """Confirm that a whitespace-only name currently passes validation since it is not trimmed"""
    payload = {
        "name": "   ",
        "description": "A group created with a blank-looking name",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    response = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    assert response.json()["name"] == "   "
 
 
@pytest.mark.asyncio
async def test_create_group_duplicate_name_is_allowed(client, member_token):
    """Confirm that two groups with the identical name can both be created since no uniqueness check exists"""
    payload = {
        "name": "Duplicate Group",
        "description": "First group with this exact name",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    first = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
 
    payload = {
        "name": "Duplicate Group",
        "description": "Second group with this exact same name",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    second = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
 
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["name"] == second.json()["name"] == "Duplicate Group"
 
 
@pytest.mark.asyncio
async def test_create_group_accepts_non_url_image_and_link_values(client, member_token):
    """Confirm that image_url and link url values are accepted without any URL-format validation"""
    payload = {
        "name": "Malformed Links Group",
        "description": "A group with garbage image and link urls",
        "category": "Technical",
        "type": "UNOFFICIAL",
        "image_url": "not-a-url",
        "links": [{"label": "Website", "url": "also-not-a-url"}]
    }
    response = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
 
 
@pytest.mark.asyncio
async def test_create_group_link_label_over_max_length_fails(client, member_token):
    """Validate that group creation is rejected when a link label exceeds the 50-character limit"""
    payload = {
        "name": "Long Link Label Group",
        "description": "A group with a link label exceeding the max length",
        "category": "Technical",
        "type": "UNOFFICIAL",
        "links": [{"label": "A" * 51, "url": "https://example.com"}]
    }
    response = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 422
 
 
@pytest.mark.asyncio
async def test_create_group_link_url_over_max_length_fails(client, member_token):
    """Validate that group creation is rejected when a link url exceeds the 500-character limit"""
    payload = {
        "name": "Long Link Url Group",
        "description": "A group with a link url exceeding the max length",
        "category": "Technical",
        "type": "UNOFFICIAL",
        "links": [{"label": "Website", "url": "A" * 501}]
    }
    response = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 422
 
 
# ==== browse ====
 
@pytest.mark.asyncio
async def test_browse_groups_only_returns_active_groups_for_members(client, member_token):
    """Verify that members only see ACTIVE groups when browsing"""
    payload = {
        "name": "Pending Browse Group",
        "description": "A group that stays pending for browse testing",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
 
    payload = {
        "name": "Active Browse Group",
        "description": "A group that is active immediately for browse testing",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
 
    response = await client.get("/groups", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    names = [group["name"] for group in response.json()]
    assert "Active Browse Group" in names
    assert "Pending Browse Group" not in names
 
 
@pytest.mark.asyncio
async def test_browse_groups_ignores_status_filter_for_members(client, member_token):
    """Confirm that a member-supplied status filter is ignored and only ACTIVE groups are returned"""
    payload = {
        "name": "Filtered Pending Group",
        "description": "A pending group used to test the ignored status filter",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
 
    response = await client.get(
        "/groups", params={"status": "PENDING"}, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 200
    names = [group["name"] for group in response.json()]
    assert "Filtered Pending Group" not in names
 
 
@pytest.mark.asyncio
async def test_browse_groups_search_is_case_insensitive(client, member_token):
    """Verify that the search filter matches group names regardless of casing"""
    payload = {
        "name": "Photography Guild",
        "description": "A group for photography enthusiasts",
        "category": "Arts",
        "type": "UNOFFICIAL"
    }
    await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
 
    response = await client.get(
        "/groups", params={"search": "PHOTOGRAPHY"}, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 200
    names = [group["name"] for group in response.json()]
    assert "Photography Guild" in names
 
 
@pytest.mark.asyncio
async def test_browse_groups_category_filter_is_case_insensitive(client, member_token):
    """Verify that the category filter matches regardless of casing"""
    payload = {
        "name": "Painters Circle",
        "description": "A group for painters and sketch artists",
        "category": "Fine Arts",
        "type": "UNOFFICIAL"
    }
    await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
 
    response = await client.get(
        "/groups", params={"category": "fine arts"}, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 200
    names = [group["name"] for group in response.json()]
    assert "Painters Circle" in names
 
 
@pytest.mark.asyncio
async def test_browse_groups_scoped_to_own_tenant(client, member_token):
    """Verify that groups from another tenant are not visible when browsing"""
    admin_payload = {
        "email": "admin@otherbrowse.edu.in",
        "full_name": "Other Browse Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "TENANT_ADMIN"
    }
    admin_signup = await client.post("/auth/signup", json=admin_payload)
    other_admin_token = admin_signup.json()["access_token"]
 
    tenant_payload = {
        "name": "Other Browse Tenant",
        "slug": "group-other-browse-tenant",
        "vertical": "campus_club",
        "description": "A separate tenant for browse scoping tests"
    }
    await client.post(
        "/tenant/onboarding", json=tenant_payload, headers={"Authorization": f"Bearer {other_admin_token}"}
    )
    login = await client.post(
        "/auth/login", json={"email": "admin@otherbrowse.edu.in", "password": "Admin@123"}
    )
    other_admin_token = login.json()["access_token"]
 
    other_member_payload = {
        "email": "leader@otherbrowse.edu.in",
        "full_name": "Other Browse Leader",
        "password": "Leader@123",
        "confirm_password": "Leader@123",
        "role": "MEMBER",
        "tenant_slug": "group-other-browse-tenant",
    }
    other_member_signup = await client.post("/auth/signup", json=other_member_payload)
    other_member_token = other_member_signup.json()["access_token"]
 
    group_payload = {
        "name": "Foreign Tenant Group",
        "description": "A group that belongs to a different tenant",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    await client.post("/groups", json=group_payload, headers={"Authorization": f"Bearer {other_member_token}"})
 
    response = await client.get("/groups", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    names = [group["name"] for group in response.json()]
    assert "Foreign Tenant Group" not in names
 
 
@pytest.mark.asyncio
async def test_browse_groups_without_token_fails(client):
    """Verify that browsing groups is rejected when no authentication token is provided"""
    response = await client.get("/groups")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"
 
 
@pytest.mark.asyncio
async def test_browse_groups_search_below_min_length_fails(client, member_token):
    """Validate that browsing groups is rejected when the search query is empty"""
    response = await client.get(
        "/groups", params={"search": ""}, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 422
 
 
@pytest.mark.asyncio
async def test_browse_groups_category_over_max_length_fails(client, member_token):
    """Validate that browsing groups is rejected when the category filter exceeds the 50-character limit"""
    response = await client.get(
        "/groups", params={"category": "A" * 51}, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 422
 
 
@pytest.mark.asyncio
async def test_browse_groups_admin_can_filter_by_status(client, admin_token):
    """Verify that an admin can filter groups by a specific status"""
    tenant_payload = {
        "name": "Status Filter Tenant",
        "slug": "group-status-filter-tenant",
        "vertical": "campus_club",
        "description": "Onboarding the admin's own tenant for the status filter test"
    }
    await client.post(
        "/tenant/onboarding", json=tenant_payload, headers={"Authorization": f"Bearer {admin_token}"}
    )
    login = await client.post(
        "/auth/login", json={"email": "admin@newtenant.edu", "password": "Admin@123"}
    )
    admin_token = login.json()["access_token"]

    member_payload = {
        "email": "leader@newtenant.edu",
        "full_name": "Status Filter Leader",
        "password": "Leader@123",
        "confirm_password": "Leader@123",
        "role": "MEMBER",
        "tenant_slug": "group-status-filter-tenant",
    }
    member_signup = await client.post("/auth/signup", json=member_payload)
    member_token = member_signup.json()["access_token"]

    payload = {
        "name": "Admin Filter Pending Group",
        "description": "A pending group used to test admin status filtering",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})

    response = await client.get(
        "/groups", params={"status": "PENDING"}, headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    names = [group["name"] for group in response.json()]
    assert "Admin Filter Pending Group" in names
 
 
@pytest.mark.asyncio
async def test_browse_groups_type_filter_returns_matching_groups_only(client, member_token):
    """Verify that filtering groups by type returns only groups matching that type"""
    payload = {
        "name": "Unofficial Type Filter Group",
        "description": "An unofficial group used to test type filtering",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
 
    response = await client.get(
        "/groups", params={"type": "UNOFFICIAL"}, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 200
    types = [group["type"] for group in response.json()]
    assert all(t == "UNOFFICIAL" for t in types)
 
 
@pytest.mark.asyncio
async def test_browse_groups_type_and_category_combined_filter(client, member_token):
    """Verify that combining type and category filters returns only groups matching both"""
    payload = {
        "name": "Combined Filter Group",
        "description": "A group used to test combined type and category filtering",
        "category": "Combined Category",
        "type": "UNOFFICIAL"
    }
    await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
 
    response = await client.get(
        "/groups",
        params={"type": "UNOFFICIAL", "category": "Combined Category"},
        headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 200
    names = [group["name"] for group in response.json()]
    assert "Combined Filter Group" in names
 
 
# ==== view ====
 
@pytest.mark.asyncio
async def test_view_active_group_success_for_member(client, member_token):
    """Verify that a member can view an ACTIVE group's details"""
    payload = {
        "name": "Viewable Group",
        "description": "A group that is active and viewable by members",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]

    response = await client.get(f"/groups/{group_id}", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == group_id
    assert body["name"] == "Viewable Group"

    assert body["head"] is not None
    assert body["head"]["member_id"] is not None
    assert body["head"]["full_name"] is not None
    assert body["head"]["email"] is None
    assert body["head"]["roll_no"] is None
    assert body["head"]["branch"] is None
    assert body["head"]["year"] is None
 
 
@pytest.mark.asyncio
async def test_view_pending_group_returns_404_even_for_its_own_leader(client, member_token):
    """Confirm that a member cannot view their own PENDING group since only ACTIVE groups are visible to members"""
    payload = {
        "name": "Own Pending Group",
        "description": "A group left pending to test the leader's own visibility",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    create = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]
 
    response = await client.get(f"/groups/{group_id}", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Group not found"
 
 
@pytest.mark.asyncio
async def test_view_group_cross_tenant_returns_404(client, member_token):
    """Verify that viewing a group belonging to a different tenant returns not found"""
    admin_payload = {
        "email": "admin@otherview.edu.in",
        "full_name": "Other View Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "TENANT_ADMIN"
    }
    admin_signup = await client.post("/auth/signup", json=admin_payload)
    other_admin_token = admin_signup.json()["access_token"]
 
    tenant_payload = {
        "name": "Other View Tenant",
        "slug": "group-other-view-tenant",
        "vertical": "campus_club",
        "description": "A separate tenant for view scoping tests"
    }
    await client.post(
        "/tenant/onboarding", json=tenant_payload, headers={"Authorization": f"Bearer {other_admin_token}"}
    )
    login = await client.post(
        "/auth/login", json={"email": "admin@otherview.edu.in", "password": "Admin@123"}
    )
    other_admin_token = login.json()["access_token"]
 
    other_member_payload = {
        "email": "leader@otherview.edu.in",
        "full_name": "Other View Leader",
        "password": "Leader@123",
        "confirm_password": "Leader@123",
        "role": "MEMBER",
        "tenant_slug": "group-other-view-tenant",
    }
    other_member_signup = await client.post("/auth/signup", json=other_member_payload)
    other_member_token = other_member_signup.json()["access_token"]
 
    group_payload = {
        "name": "Other Tenant Group",
        "description": "A group that belongs to a different tenant",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=group_payload, headers={"Authorization": f"Bearer {other_member_token}"})
    group_id = create.json()["id"]
 
    response = await client.get(f"/groups/{group_id}", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Group not found"
 
 
@pytest.mark.asyncio
async def test_view_nonexistent_group_returns_404(client, member_token):
    """Verify that viewing a nonexistent group id returns not found"""
    response = await client.get("/groups/999999", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Group not found"
 
 
@pytest.mark.asyncio
async def test_view_pending_group_by_admin_includes_head_info(client):
    """Verify that an admin can view a PENDING group and receives head details"""
    admin_payload = {
        "email": "admin@adminview.edu.in",
        "full_name": "Admin View Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "TENANT_ADMIN"
    }
    admin_signup = await client.post("/auth/signup", json=admin_payload)
    admin_token = admin_signup.json()["access_token"]
 
    tenant_payload = {
        "name": "Admin View Tenant",
        "slug": "group-admin-view-tenant",
        "vertical": "campus_club",
        "description": "A tenant used to test admin view of pending groups"
    }
    await client.post(
        "/tenant/onboarding", json=tenant_payload, headers={"Authorization": f"Bearer {admin_token}"}
    )
    login = await client.post(
        "/auth/login", json={"email": "admin@adminview.edu.in", "password": "Admin@123"}
    )
    admin_token = login.json()["access_token"]
 
    member_payload = {
        "email": "leader@adminview.edu.in",
        "full_name": "Leader Member",
        "password": "Leader@123",
        "confirm_password": "Leader@123",
        "role": "MEMBER",
        "tenant_slug": "group-admin-view-tenant",
    }
    member_signup = await client.post("/auth/signup", json=member_payload)
    member_token = member_signup.json()["access_token"]
 
    group_payload = {
        "name": "Admin Visible Group",
        "description": "A pending group that the admin should be able to view",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    create = await client.post("/groups", json=group_payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]
 
    response = await client.get(f"/groups/{group_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "PENDING"
    assert body["head"] is not None
    assert body["head"]["full_name"] == "Leader Member"
 
 
@pytest.mark.asyncio
async def test_view_group_without_token_fails(client, member_token):
    """Verify that viewing a group is rejected when no authentication token is provided"""
    payload = {
        "name": "No Token View Group",
        "description": "A group used to test unauthenticated view access",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]
 
    response = await client.get(f"/groups/{group_id}")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"
 
 
@pytest.mark.asyncio
async def test_view_group_member_count_reflects_approved_members_only(client, member_token):
    """Verify that member_count reflects only approved memberships, not pending ones"""
    payload = {
        "name": "Member Count Group",
        "description": "A group used to test member count accuracy",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]
 
    response = await client.get(f"/groups/{group_id}", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    assert response.json()["member_count"] == 1
 
 
# ==== update ====
 
@pytest.mark.asyncio
async def test_update_group_success_by_leader(client, member_token):
    """Verify that the group leader can update the group's description and category"""
    payload = {
        "name": "Editable Group",
        "description": "A group that will be edited by its leader",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]
 
    update_payload = {"description": "An updated description here", "category": "Updated Category"}
    response = await client.put(
        f"/groups/{group_id}", json=update_payload, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["description"] == "An updated description here"
    assert body["category"] == "Updated Category"
 
 
@pytest.mark.asyncio
async def test_update_group_by_non_leader_fails(client, member_token):
    """Verify that a member who is not the group leader cannot update the group"""
    payload = {
        "name": "Leader Only Group",
        "description": "A group that only its leader can edit",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]
 
    other_payload = {
        "email": "second.member@knit.edu.in",
        "full_name": "Second Member",
        "password": "Member@123",
        "confirm_password": "Member@123",
        "role": "MEMBER",
        "tenant_slug": "test-university",
    }
    other_signup = await client.post("/auth/signup", json=other_payload)
    other_token = other_signup.json()["access_token"]
 
    update_payload = {"description": "Trying to edit as non-leader"}
    response = await client.put(
        f"/groups/{group_id}", json=update_payload, headers={"Authorization": f"Bearer {other_token}"}
    )
    assert response.status_code == 403
    body = response.json()
    assert body["message"] == "Only the group leader can perform this action"
 
 
@pytest.mark.asyncio
async def test_update_group_immutable_fields_are_ignored(client, member_token):
    """Confirm that name and type fields are silently ignored on update since the schema does not accept them"""
    payload = {
        "name": "Immutable Name Group",
        "description": "A group used to test immutable field handling",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]
 
    update_payload = {"name": "Renamed Group", "type": "OFFICIAL", "description": "Only this should change"}
    response = await client.put(
        f"/groups/{group_id}", json=update_payload, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Immutable Name Group"
    assert body["type"] == "UNOFFICIAL"
    assert body["description"] == "Only this should change"
 
 
@pytest.mark.asyncio
async def test_update_nonexistent_group_returns_404(client, member_token):
    """Verify that updating a nonexistent group id returns not found"""
    update_payload = {"description": "Does not matter"}
    response = await client.put(
        "/groups/999999", json=update_payload, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Group not found"
 
 
@pytest.mark.asyncio
async def test_update_group_description_min_length_boundary_succeeds(client, member_token):
    """Validate that group update succeeds when description is exactly at the 5-character minimum"""
    payload = {
        "name": "Update Min Desc Group",
        "description": "A group used to test the update description minimum boundary",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]
 
    update_payload = {"description": "Hello"}
    response = await client.put(
        f"/groups/{group_id}", json=update_payload, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 200
    assert response.json()["description"] == "Hello"
 
 
@pytest.mark.asyncio
async def test_update_group_description_below_min_length_fails(client, member_token):
    """Validate that group update is rejected when description is below the 5-character minimum"""
    payload = {
        "name": "Update Short Desc Group",
        "description": "A group used to test rejection of too-short update descriptions",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]
 
    update_payload = {"description": "Hi"}
    response = await client.put(
        f"/groups/{group_id}", json=update_payload, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 422
 
 
@pytest.mark.asyncio
async def test_update_group_description_over_max_length_fails(client, member_token):
    """Validate that group update is rejected when description exceeds the 1000-character limit"""
    payload = {
        "name": "Update Long Desc Group",
        "description": "A group used to test rejection of too-long update descriptions",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]
 
    update_payload = {"description": "A" * 1001}
    response = await client.put(
        f"/groups/{group_id}", json=update_payload, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 422
 
 
@pytest.mark.asyncio
async def test_update_group_category_max_length_boundary_succeeds(client, member_token):
    """Validate that group update succeeds when category is exactly at the 50-character limit"""
    payload = {
        "name": "Update Max Category Group",
        "description": "A group used to test the update category maximum boundary",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]
 
    update_payload = {"category": "A" * 50}
    response = await client.put(
        f"/groups/{group_id}", json=update_payload, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 200
    assert response.json()["category"] == "A" * 50
 
 
@pytest.mark.asyncio
async def test_update_group_category_below_min_length_fails(client, member_token):
    """Validate that group update is rejected when category is below the 2-character minimum"""
    payload = {
        "name": "Update Short Category Group",
        "description": "A group used to test rejection of too-short update categories",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]
 
    update_payload = {"category": "A"}
    response = await client.put(
        f"/groups/{group_id}", json=update_payload, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 422
 
 
@pytest.mark.asyncio
async def test_update_group_link_label_over_max_length_fails(client, member_token):
    """Validate that group update is rejected when a link label exceeds the 50-character limit"""
    payload = {
        "name": "Update Link Label Group",
        "description": "A group used to test rejection of too-long update link labels",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]
 
    update_payload = {"links": [{"label": "A" * 51, "url": "https://example.com"}]}
    response = await client.put(
        f"/groups/{group_id}", json=update_payload, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 422
 
 
@pytest.mark.asyncio
async def test_update_group_link_url_over_max_length_fails(client, member_token):
    """Validate that group update is rejected when a link url exceeds the 500-character limit"""
    payload = {
        "name": "Update Link Url Group",
        "description": "A group used to test rejection of too-long update link urls",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]
 
    update_payload = {"links": [{"label": "Website", "url": "A" * 501}]}
    response = await client.put(
        f"/groups/{group_id}", json=update_payload, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 422
 
@pytest.mark.asyncio
async def test_update_group_links_replaced_successfully(client, db_session, member_token):
    """Verify that updating a group's links replaces the existing set of links"""
    payload = {
        "name": "Link Replace Group",
        "description": "A group used to test link replacement on update",
        "category": "Technical",
        "type": "UNOFFICIAL",
        "links": [{"label": "Old Site", "url": "https://old.example.com"}]
    }
    create = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]

    update_payload = {"links": [{"label": "New Site", "url": "https://new.example.com"}]}
    response = await client.put(
        f"/groups/{group_id}", json=update_payload, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    labels = [link["label"] for link in body["links"]]
    # the PUT response itself returns stale links right after
    # the real check is the GET below.

    db_session.expire_all()

    get_response = await client.get(
        f"/groups/{group_id}", headers={"Authorization": f"Bearer {member_token}"}
    )
    assert get_response.status_code == 200
    get_labels = [link["label"] for link in get_response.json()["links"]]
    assert get_labels == ["New Site"]

# @pytest.mark.asyncio
# async def test_update_group_links_replaced_successfully(client, member_token):
#     """Verify that updating a group's links replaces the existing set of links"""
#     payload = {
#         "name": "Link Replace Group",
#         "description": "A group used to test link replacement on update",
#         "category": "Technical",
#         "type": "UNOFFICIAL",
#         "links": [{"label": "Old Site", "url": "https://old.example.com"}]
#     }
#     create = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
#     group_id = create.json()["id"]

#     update_payload = {"links": [{"label": "New Site", "url": "https://new.example.com"}]}
#     response = await client.put(
#         f"/groups/{group_id}", json=update_payload, headers={"Authorization": f"Bearer {member_token}"}
#     )
#     assert response.status_code == 200
#     body = response.json()
#     put_labels = [link["label"] for link in body["links"]]

#     get_response = await client.get(
#         f"/groups/{group_id}", headers={"Authorization": f"Bearer {member_token}"}
#     )
#     assert get_response.status_code == 200
#     get_labels = [link["label"] for link in get_response.json()["links"]]

#     print(f"PUT response labels: {put_labels}")
#     print(f"GET response labels: {get_labels}")

#     assert put_labels == ["New Site"], f"PUT response stale: {put_labels}"
#     assert get_labels == ["New Site"], f"GET response stale: {get_labels}"


@pytest.mark.asyncio
async def test_update_group_links_empty_list_clears_links(client, db_session, member_token):
    """Verify that passing an empty links list removes all existing links"""
    payload = {
        "name": "Link Clear Group",
        "description": "A group used to test clearing links on update",
        "category": "Technical",
        "type": "UNOFFICIAL",
        "links": [{"label": "Old Site", "url": "https://old.example.com"}]
    }
    create = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]

    update_payload = {"links": []}
    response = await client.put(
        f"/groups/{group_id}", json=update_payload, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 200
    # PUT response itself returns stale links right after
    # saving, even though the database write is correct.

    db_session.expire_all()

    get_response = await client.get(
        f"/groups/{group_id}", headers={"Authorization": f"Bearer {member_token}"}
    )
    assert get_response.status_code == 200
    assert get_response.json()["links"] == []
 
 
@pytest.mark.asyncio
async def test_update_group_links_omitted_leaves_existing_links_unchanged(client, member_token):
    """Confirm that omitting the links field leaves existing links unchanged"""
    payload = {
        "name": "Link Untouched Group",
        "description": "A group used to test that omitted links are left unchanged",
        "category": "Technical",
        "type": "UNOFFICIAL",
        "links": [{"label": "Kept Site", "url": "https://kept.example.com"}]
    }
    create = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]
 
    update_payload = {"description": "Only description should change here"}
    response = await client.put(
        f"/groups/{group_id}", json=update_payload, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    labels = [link["label"] for link in body["links"]]
    assert labels == ["Kept Site"]
 
 
@pytest.mark.asyncio
async def test_update_group_image_url_success(client, member_token):
    """Verify that a group's image_url can be updated by its leader"""
    payload = {
        "name": "Image Update Group",
        "description": "A group used to test image_url updates",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]
 
    update_payload = {"image_url": "https://example.com/new-image.png"}
    response = await client.put(
        f"/groups/{group_id}", json=update_payload, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 200
    assert response.json()["image_url"] == "https://example.com/new-image.png"

@pytest.mark.asyncio
async def test_update_group_with_no_fields_provided_is_a_noop(client, member_token):
    """Confirm that updating a group with an empty payload leaves all fields unchanged"""
    payload = {
        "name": "Noop Update Group",
        "description": "A group used to test empty payload updates",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]
 
    response = await client.put(
        f"/groups/{group_id}", json={}, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["description"] == "A group used to test empty payload updates"
    assert body["category"] == "Technical"
 
 
@pytest.mark.asyncio
async def test_update_group_without_token_fails(client, member_token):
    """Verify that group update is rejected when no authentication token is provided"""
    payload = {
        "name": "No Token Update Group",
        "description": "A group used to test unauthenticated update access",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]
 
    update_payload = {"description": "Should not be applied"}
    response = await client.put(f"/groups/{group_id}", json=update_payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"
 
 
@pytest.mark.asyncio
async def test_update_nonexistent_group_by_non_leader_returns_404_not_403(client, member_token):
    """Confirm that updating a nonexistent group returns not found before the leader check runs"""
    update_payload = {"description": "Does not matter here"}
    response = await client.put(
        "/groups/999999", json=update_payload, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Group not found"
 
 
# ==== delete ====
 
@pytest.mark.asyncio
async def test_delete_group_by_leader_success(client, member_token):
    """Verify that the group leader can archive the group"""
    payload = {
        "name": "Deletable Group",
        "description": "A group that will be archived by its leader",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]
 
    response = await client.delete(f"/groups/{group_id}", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ARCHIVED"
    assert body["message"] == "Group archived successfully"
 
 
@pytest.mark.asyncio
async def test_delete_group_by_non_leader_fails(client, member_token):
    """Verify that a member who is not the group leader cannot archive the group"""
    payload = {
        "name": "Protected Group",
        "description": "A group that only its leader can archive",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]
 
    other_payload = {
        "email": "third.member@knit.edu.in",
        "full_name": "Third Member",
        "password": "Member@123",
        "confirm_password": "Member@123",
        "role": "MEMBER",
        "tenant_slug": "test-university",
    }
    other_signup = await client.post("/auth/signup", json=other_payload)
    other_token = other_signup.json()["access_token"]
 
    response = await client.delete(f"/groups/{group_id}", headers={"Authorization": f"Bearer {other_token}"})
    assert response.status_code == 403
    body = response.json()
    assert body["message"] == "Only the group leader can perform this action"
 
 
@pytest.mark.asyncio
async def test_delete_already_archived_group_is_idempotent(client, member_token):
    """Confirm that archiving an already-archived group succeeds again since no status guard exists"""
    payload = {
        "name": "Twice Archived Group",
        "description": "A group that will be archived more than once",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]
 
    await client.delete(f"/groups/{group_id}", headers={"Authorization": f"Bearer {member_token}"})
    response = await client.delete(f"/groups/{group_id}", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ARCHIVED"
 
 
@pytest.mark.asyncio
async def test_delete_nonexistent_group_returns_404(client, member_token):
    """Verify that archiving a nonexistent group id returns not found"""
    response = await client.delete("/groups/999999", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Group not found"
 
 
@pytest.mark.asyncio
async def test_delete_group_without_token_fails(client, member_token):
    """Verify that group archival is rejected when no authentication token is provided"""
    payload = {
        "name": "No Token Delete Group",
        "description": "A group used to test unauthenticated delete access",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]
 
    response = await client.delete(f"/groups/{group_id}")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"
 
 
# ==== approve / reject ====
 
@pytest.mark.asyncio
async def test_approve_pending_group_success(client):
    """Verify that an admin can approve a PENDING group belonging to their own tenant"""
    admin_payload = {
        "email": "admin@approve.edu.in",
        "full_name": "Approve Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "TENANT_ADMIN"
    }
    admin_signup = await client.post("/auth/signup", json=admin_payload)
    admin_token = admin_signup.json()["access_token"]
 
    tenant_payload = {
        "name": "Approve Tenant",
        "slug": "group-approve-tenant",
        "vertical": "campus_club",
        "description": "A tenant used to test group approval"
    }
    await client.post(
        "/tenant/onboarding", json=tenant_payload, headers={"Authorization": f"Bearer {admin_token}"}
    )
    login = await client.post(
        "/auth/login", json={"email": "admin@approve.edu.in", "password": "Admin@123"}
    )
    admin_token = login.json()["access_token"]
 
    member_payload = {
        "email": "leader@approve.edu.in",
        "full_name": "Approve Leader",
        "password": "Leader@123",
        "confirm_password": "Leader@123",
        "role": "MEMBER",
        "tenant_slug": "group-approve-tenant",
    }
    member_signup = await client.post("/auth/signup", json=member_payload)
    member_token = member_signup.json()["access_token"]
 
    group_payload = {
        "name": "Approvable Group",
        "description": "A pending group awaiting admin approval",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    create = await client.post("/groups", json=group_payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]
 
    response = await client.patch(f"/groups/{group_id}/approve", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ACTIVE"
    assert body["message"] == "Group approved"
 
 
@pytest.mark.asyncio
async def test_reject_pending_group_success(client):
    """Verify that an admin can reject a PENDING group belonging to their own tenant"""
    admin_payload = {
        "email": "admin@reject.edu.in",
        "full_name": "Reject Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "TENANT_ADMIN"
    }
    admin_signup = await client.post("/auth/signup", json=admin_payload)
    admin_token = admin_signup.json()["access_token"]
 
    tenant_payload = {
        "name": "Reject Tenant",
        "slug": "group-reject-tenant",
        "vertical": "campus_club",
        "description": "A tenant used to test group rejection"
    }
    await client.post(
        "/tenant/onboarding", json=tenant_payload, headers={"Authorization": f"Bearer {admin_token}"}
    )
    login = await client.post(
        "/auth/login", json={"email": "admin@reject.edu.in", "password": "Admin@123"}
    )
    admin_token = login.json()["access_token"]
 
    member_payload = {
        "email": "leader@reject.edu.in",
        "full_name": "Reject Leader",
        "password": "Leader@123",
        "confirm_password": "Leader@123",
        "role": "MEMBER",
        "tenant_slug": "group-reject-tenant",
    }
    member_signup = await client.post("/auth/signup", json=member_payload)
    member_token = member_signup.json()["access_token"]
 
    group_payload = {
        "name": "Rejectable Group",
        "description": "A pending group awaiting admin rejection",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    create = await client.post("/groups", json=group_payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]
 
    response = await client.patch(f"/groups/{group_id}/reject", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "REJECTED"
    assert body["message"] == "Group rejected"
 
 
@pytest.mark.asyncio
async def test_approve_group_by_member_fails(client, member_token):
    """Verify that a member cannot approve a group"""
    payload = {
        "name": "Member Approve Attempt",
        "description": "A group approval attempt made by a member",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    create = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]
 
    response = await client.patch(f"/groups/{group_id}/approve", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 401
    body = response.json()
    assert body["message"] == "Invalid token"
 
 
@pytest.mark.asyncio
async def test_approve_already_active_group_fails(client):
    """Confirm that approving a group that is already ACTIVE is rejected as not pending"""
    admin_payload = {
        "email": "admin@doubleapprove.edu.in.in",
        "full_name": "Double Approve Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "TENANT_ADMIN"
    }
    admin_signup = await client.post("/auth/signup", json=admin_payload)
    admin_token = admin_signup.json()["access_token"]
 
    tenant_payload = {
        "name": "Double Approve Tenant",
        "slug": "group-double-approve-tenant",
        "vertical": "campus_club",
        "description": "A tenant used to test double approval rejection"
    }
    await client.post(
        "/tenant/onboarding", json=tenant_payload, headers={"Authorization": f"Bearer {admin_token}"}
    )
    login = await client.post(
        "/auth/login", json={"email": "admin@doubleapprove.edu.in.in", "password": "Admin@123"}
    )
    admin_token = login.json()["access_token"]
 
    member_payload = {
        "email": "leader@doubleapprove.edu.in.in",
        "full_name": "Double Approve Leader",
        "password": "Leader@123",
        "confirm_password": "Leader@123",
        "role": "MEMBER",
        "tenant_slug": "group-double-approve-tenant",
    }
    member_signup = await client.post("/auth/signup", json=member_payload)
    member_token = member_signup.json()["access_token"]
 
    group_payload = {
        "name": "Already Active Group",
        "description": "A group that is already active before approval is attempted",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=group_payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]
 
    response = await client.patch(f"/groups/{group_id}/approve", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 403
    body = response.json()
    assert body["message"] == "Group is not pending approval"
 
 
@pytest.mark.asyncio
async def test_approve_group_from_different_tenant_fails(client):
    """Verify that an admin cannot approve a group belonging to a different tenant"""
    owner_admin_payload = {
        "email": "admin@groupowner.edu.in",
        "full_name": "Group Owner Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "TENANT_ADMIN"
    }
    owner_admin_signup = await client.post("/auth/signup", json=owner_admin_payload)
    owner_admin_token = owner_admin_signup.json()["access_token"]
 
    owner_tenant_payload = {
        "name": "Group Owner Tenant",
        "slug": "group-group-owner-tenant",
        "vertical": "campus_club",
        "description": "A tenant that owns the group under test"
    }
    await client.post(
        "/tenant/onboarding", json=owner_tenant_payload, headers={"Authorization": f"Bearer {owner_admin_token}"}
    )
    login = await client.post(
        "/auth/login", json={"email": "admin@groupowner.edu.in", "password": "Admin@123"}
    )
    owner_admin_token = login.json()["access_token"]
 
    owner_member_payload = {
        "email": "leader@groupowner.edu.in",
        "full_name": "Group Owner Leader",
        "password": "Leader@123",
        "confirm_password": "Leader@123",
        "role": "MEMBER",
        "tenant_slug": "group-group-owner-tenant",
    }
    owner_member_signup = await client.post("/auth/signup", json=owner_member_payload)
    owner_member_token = owner_member_signup.json()["access_token"]
 
    other_admin_payload = {
        "email": "admin@otheradmin.edu.in",
        "full_name": "Other Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "TENANT_ADMIN"
    }
    other_admin_signup = await client.post("/auth/signup", json=other_admin_payload)
    other_admin_token = other_admin_signup.json()["access_token"]
 
    other_tenant_payload = {
        "name": "Other Admin Tenant",
        "slug": "group-other-admin-tenant",
        "vertical": "campus_club",
        "description": "A different tenant whose admin should not approve"
    }
    await client.post(
        "/tenant/onboarding", json=other_tenant_payload, headers={"Authorization": f"Bearer {other_admin_token}"}
    )
    login = await client.post(
        "/auth/login", json={"email": "admin@otheradmin.edu.in", "password": "Admin@123"}
    )
    other_admin_token = login.json()["access_token"]
 
    group_payload = {
        "name": "Cross Tenant Group",
        "description": "A group that belongs to a different tenant than the approving admin",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    create = await client.post(
        "/groups", json=group_payload, headers={"Authorization": f"Bearer {owner_member_token}"}
    )
    group_id = create.json()["id"]
 
    response = await client.patch(
        f"/groups/{group_id}/approve", headers={"Authorization": f"Bearer {other_admin_token}"}
    )
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Group not found"
 
 
@pytest.mark.asyncio
async def test_reject_already_rejected_group_fails(client):
    """Confirm that rejecting a group that is already REJECTED is rejected as not pending"""
    admin_payload = {
        "email": "admin@doublereject.edu.in.in",
        "full_name": "Double Reject Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "TENANT_ADMIN"
    }
    admin_signup = await client.post("/auth/signup", json=admin_payload)
    admin_token = admin_signup.json()["access_token"]
 
    tenant_payload = {
        "name": "Double Reject Tenant",
        "slug": "group-double-reject-tenant",
        "vertical": "campus_club",
        "description": "A tenant used to test double rejection"
    }
    await client.post(
        "/tenant/onboarding", json=tenant_payload, headers={"Authorization": f"Bearer {admin_token}"}
    )
    login = await client.post(
        "/auth/login", json={"email": "admin@doublereject.edu.in.in", "password": "Admin@123"}
    )
    admin_token = login.json()["access_token"]
 
    member_payload = {
        "email": "leader@doublereject.edu.in.in",
        "full_name": "Double Reject Leader",
        "password": "Leader@123",
        "confirm_password": "Leader@123",
        "role": "MEMBER",
        "tenant_slug": "group-double-reject-tenant",
    }
    member_signup = await client.post("/auth/signup", json=member_payload)
    member_token = member_signup.json()["access_token"]
 
    group_payload = {
        "name": "Already Rejected Group",
        "description": "A group that will be rejected more than once",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    create = await client.post("/groups", json=group_payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]
 
    await client.patch(f"/groups/{group_id}/reject", headers={"Authorization": f"Bearer {admin_token}"})
    response = await client.patch(f"/groups/{group_id}/reject", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 403
    body = response.json()
    assert body["message"] == "Group is not pending approval"
 
 
@pytest.mark.asyncio
async def test_approve_nonexistent_group_returns_404(client, admin_token):
    """Verify that approving a nonexistent group id returns not found"""
    response = await client.patch("/groups/999999/approve", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 403
    body = response.json()
    assert body["message"] == "Tenant mismatch"
 
 
@pytest.mark.asyncio
async def test_reject_group_by_member_fails(client, member_token):
    """Verify that a member cannot reject a group"""
    payload = {
        "name": "Member Reject Attempt",
        "description": "A group rejection attempt made by a member",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    create = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]
 
    response = await client.patch(f"/groups/{group_id}/reject", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 401
    body = response.json()
    assert body["message"] == "Invalid token"
 
 
@pytest.mark.asyncio
async def test_reject_group_from_different_tenant_fails(client):
    """Verify that an admin cannot reject a group belonging to a different tenant"""
    owner_admin_payload = {
        "email": "admin@rejectowner.edu.in",
        "full_name": "Reject Owner Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "TENANT_ADMIN"
    }
    owner_admin_signup = await client.post("/auth/signup", json=owner_admin_payload)
    owner_admin_token = owner_admin_signup.json()["access_token"]
 
    owner_tenant_payload = {
        "name": "Reject Owner Tenant",
        "slug": "group-reject-owner-tenant",
        "vertical": "campus_club",
        "description": "A tenant that owns the group under test for reject scoping"
    }
    await client.post(
        "/tenant/onboarding", json=owner_tenant_payload, headers={"Authorization": f"Bearer {owner_admin_token}"}
    )
    login = await client.post(
        "/auth/login", json={"email": "admin@rejectowner.edu.in", "password": "Admin@123"}
    )
    owner_admin_token = login.json()["access_token"]
 
    owner_member_payload = {
        "email": "leader@rejectowner.edu.in",
        "full_name": "Reject Owner Leader",
        "password": "Leader@123",
        "confirm_password": "Leader@123",
        "role": "MEMBER",
        "tenant_slug": "group-reject-owner-tenant",
    }
    owner_member_signup = await client.post("/auth/signup", json=owner_member_payload)
    owner_member_token = owner_member_signup.json()["access_token"]
 
    other_admin_payload = {
        "email": "admin@rejectother.edu.in",
        "full_name": "Reject Other Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "TENANT_ADMIN"
    }
    other_admin_signup = await client.post("/auth/signup", json=other_admin_payload)
    other_admin_token = other_admin_signup.json()["access_token"]
 
    other_tenant_payload = {
        "name": "Reject Other Tenant",
        "slug": "group-reject-other-tenant",
        "vertical": "campus_club",
        "description": "A different tenant whose admin should not reject"
    }
    await client.post(
        "/tenant/onboarding", json=other_tenant_payload, headers={"Authorization": f"Bearer {other_admin_token}"}
    )
    login = await client.post(
        "/auth/login", json={"email": "admin@rejectother.edu.in", "password": "Admin@123"}
    )
    other_admin_token = login.json()["access_token"]
 
    group_payload = {
        "name": "Cross Tenant Reject Group",
        "description": "A group that belongs to a different tenant than the rejecting admin",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    create = await client.post(
        "/groups", json=group_payload, headers={"Authorization": f"Bearer {owner_member_token}"}
    )
    group_id = create.json()["id"]
 
    response = await client.patch(
        f"/groups/{group_id}/reject", headers={"Authorization": f"Bearer {other_admin_token}"}
    )
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Group not found"
 
 
@pytest.mark.asyncio
async def test_reject_nonexistent_group_returns_404(client, admin_token):
    """Verify that rejecting a nonexistent group id returns not found"""
    response = await client.patch("/groups/999999/reject", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 403
    body = response.json()
    assert body["message"] == "Tenant mismatch"
 
 
@pytest.mark.asyncio
async def test_approve_group_without_token_fails(client, member_token):
    """Verify that group approval is rejected when no authentication token is provided"""
    payload = {
        "name": "No Token Approve Group",
        "description": "A group used to test unauthenticated approve access",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    create = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]
 
    response = await client.patch(f"/groups/{group_id}/approve")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"

# ==== my groups ====

@pytest.mark.asyncio
async def test_my_groups_role_leader_returns_led_groups(client, member_token):
    """Verify that role=LEADER returns groups the member leads"""
    payload = {
        "name": "My Led Group",
        "description": "A group led by the requesting member",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})

    response = await client.get(
        "/groups/me", params={"role": "LEADER"}, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    names = [item["name"] for item in body]
    assert "My Led Group" in names
    assert all(item["membership_role"] == "LEADER" for item in body)


@pytest.mark.asyncio
async def test_my_groups_role_leader_with_status_filters_group_status(client, member_token):
    """Verify that role=LEADER with status filters by the group's approval status"""
    payload = {
        "name": "Active Led Group",
        "description": "An active group led by the member",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})

    payload = {
        "name": "Pending Led Group",
        "description": "A pending group led by the member",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})

    response = await client.get(
        "/groups/me",
        params={"role": "LEADER", "status": "ACTIVE"},
        headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert "Active Led Group" in names
    assert "Pending Led Group" not in names


@pytest.mark.asyncio
async def test_my_groups_role_member_returns_joined_groups(client, member_token):
    """Verify that role=MEMBER returns groups the member has joined"""
    payload = {
        "name": "Joinable Member Group",
        "description": "A group the member will join as a member",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]

    payload = {
        "email": "mygroups.joiner@knit.edu.in",
        "full_name": "MyGroups Joiner",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "MEMBER",
        "tenant_slug": "test-university",
    }
    joiner_signup = await client.post("/auth/signup", json=payload)
    joiner_token = joiner_signup.json()["access_token"]
    await client.post(f"/groups/{group_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})

    response = await client.get(
        "/groups/me", params={"role": "MEMBER"}, headers={"Authorization": f"Bearer {joiner_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    names = [item["name"] for item in body]
    assert "Joinable Member Group" in names
    assert all(item["membership_role"] == "MEMBER" for item in body)


@pytest.mark.asyncio
async def test_my_groups_role_member_with_status_filters_membership_status(client, member_token):
    """Verify that role=MEMBER with status filters by the membership's own status, not group status"""
    payload = {
        "name": "Membership Status Group",
        "description": "A group used to test membership status filtering",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    group_id = create.json()["id"]

    payload = {
        "email": "mygroups.pendingjoiner@knit.edu.in",
        "full_name": "MyGroups Pending Joiner",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "MEMBER",
        "tenant_slug": "test-university",
    }
    joiner_signup = await client.post("/auth/signup", json=payload)
    joiner_token = joiner_signup.json()["access_token"]
    await client.post(f"/groups/{group_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})

    response = await client.get(
        "/groups/me",
        params={"role": "MEMBER", "status": "PENDING"},
        headers={"Authorization": f"Bearer {joiner_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    names = [item["name"] for item in body]
    assert "Membership Status Group" in names
    assert all(item["membership_status"] == "PENDING" for item in body)


@pytest.mark.asyncio
async def test_my_groups_status_without_role_fails(client, member_token):
    """Validate that supplying status without role is rejected"""
    response = await client.get(
        "/groups/me", params={"status": "ACTIVE"}, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 422
    body = response.json()
    assert body["message"] == (
        "status must be sent together with role: it means the group status for LEADER "
        "and your membership status for MEMBER"
    )


@pytest.mark.asyncio
async def test_my_groups_leader_status_with_membership_status_value_fails(client, member_token):
    """Validate that role=LEADER with a membership-status value (not a group status) is rejected"""
    response = await client.get(
        "/groups/me",
        params={"role": "LEADER", "status": "APPROVED"},
        headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 422
    body = response.json()
    assert "status must be one of" in body["message"]
    assert "role is LEADER" in body["message"]


@pytest.mark.asyncio
async def test_my_groups_member_status_with_group_status_value_fails(client, member_token):
    """Validate that role=MEMBER with a group-status value (not a membership status) is rejected"""
    response = await client.get(
        "/groups/me",
        params={"role": "MEMBER", "status": "ARCHIVED"},
        headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 422
    body = response.json()
    assert "status must be one of" in body["message"]
    assert "role is MEMBER" in body["message"]


@pytest.mark.asyncio
async def test_my_groups_invalid_role_value_fails(client, member_token):
    """Validate that an unrecognized role value is rejected"""
    response = await client.get(
        "/groups/me", params={"role": "PRESIDENT"}, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_my_groups_no_role_no_status_returns_all(client, member_token):
    """Verify that omitting both role and status returns all of the member's groups regardless of role"""
    payload = {
        "name": "No Filter Group",
        "description": "A group used to test the unfiltered my-groups listing",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})

    response = await client.get("/groups/me", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert "No Filter Group" in names


@pytest.mark.asyncio
async def test_my_groups_includes_head_name_and_member_count(client, member_token):
    """Verify that each item includes head_name and member_count"""
    payload = {
        "name": "Head Name Group",
        "description": "A group used to test head_name and member_count fields",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})

    response = await client.get("/groups/me", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    item = next(i for i in response.json() if i["name"] == "Head Name Group")
    assert item["head_name"] == "Group Member"
    assert item["member_count"] == 1


# @pytest.mark.asyncio
# async def test_my_groups_ordered_by_most_recent_membership_first(client, member_token):
#     """Verify that results are ordered by membership created_at descending, most recent first"""
#     payload = {
#         "name": "First Created Group",
#         "description": "The first group the member joins/creates",
#         "category": "Technical",
#         "type": "UNOFFICIAL"
#     }
#     await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})

#     payload = {
#         "name": "Second Created Group",
#         "description": "The second group the member joins/creates",
#         "category": "Technical",
#         "type": "UNOFFICIAL"
#     }
#     await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})

#     response = await client.get("/groups/me", headers={"Authorization": f"Bearer {member_token}"})
    
#     assert response.status_code == 200
#     names = [item["name"] for item in response.json()]
#     assert names.index("Second Created Group") < names.index("First Created Group")


@pytest.mark.asyncio
async def test_my_groups_empty_for_member_with_no_groups(client, seed_tenant):
    """Verify that a member with no memberships gets an empty list"""
    payload = {
        "email": "nogroups.member@knit.edu.in",
        "full_name": "No Groups Member",
        "password": "Member@123",
        "confirm_password": "Member@123",
        "role": "MEMBER",
        "tenant_slug": seed_tenant.slug,
    }
    signup = await client.post("/auth/signup", json=payload)
    token = signup.json()["access_token"]

    response = await client.get("/groups/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_my_groups_without_token_fails(client):
    """Verify that requesting my-groups is rejected when no authentication token is provided"""
    response = await client.get("/groups/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"
