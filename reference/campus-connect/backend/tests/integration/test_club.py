
import pytest
 
 
# ==== create ====
 
@pytest.mark.asyncio
async def test_create_official_club_pending_approval(client, student_token):
    """Verify that creating an OFFICIAL club succeeds and leaves it pending admin approval"""
    payload = {
        "name": "Robotics Club",
        "description": "A club for robotics enthusiasts and builders",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    response = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Robotics Club"
    assert body["type"] == "OFFICIAL"
    assert body["status"] == "PENDING"
    assert body["message"] == "Club submitted for admin approval"
 
 
@pytest.mark.asyncio
async def test_create_unofficial_club_active_immediately(client, student_token):
    """Verify that creating an UNOFFICIAL club succeeds and is active immediately"""
    payload = {
        "name": "Chess Circle",
        "description": "A club for chess enthusiasts and casual players",
        "category": "Games",
        "type": "UNOFFICIAL"
    }
    response = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Chess Circle"
    assert body["type"] == "UNOFFICIAL"
    assert body["status"] == "ACTIVE"
    assert body["message"] == "Club created and is now live"
 
 
@pytest.mark.asyncio
async def test_create_club_links_empty_array_succeeds(client, student_token):
    """Verify that a club can be created with no links provided"""
    payload = {
        "name": "Linkless Club",
        "description": "A club created without any links",
        "category": "Technical",
        "type": "UNOFFICIAL",
        "links": []
    }
    response = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Linkless Club"
 
 
@pytest.mark.asyncio
async def test_create_club_name_min_length_boundary_succeeds(client, student_token):
    """Validate that club creation succeeds when the name is exactly at the 3-character minimum"""
    payload = {
        "name": "Abc",
        "description": "A club with a very short name for testing",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    response = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    assert response.json()["name"] == "Abc"
 
 
@pytest.mark.asyncio
async def test_create_club_name_below_min_length_fails(client, student_token):
    """Validate that club creation is rejected when the name is below the 3-character minimum"""
    payload = {
        "name": "Ab",
        "description": "A club with a name that is too short",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    response = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 422
 
 
@pytest.mark.asyncio
async def test_create_club_name_max_length_boundary_succeeds(client, student_token):
    """Validate that club creation succeeds when the name is exactly at the 100-character limit"""
    payload = {
        "name": "A" * 100,
        "description": "A club with a name exactly at the max length",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    response = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    assert response.json()["name"] == "A" * 100
 
 
@pytest.mark.asyncio
async def test_create_club_name_over_max_length_fails(client, student_token):
    """Validate that club creation is rejected when the name exceeds the 100-character limit"""
    payload = {
        "name": "A" * 101,
        "description": "A club with a name exceeding the max length",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    response = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 422
 
 
@pytest.mark.asyncio
async def test_create_club_description_min_length_boundary_succeeds(client, student_token):
    """Validate that club creation succeeds when the description is exactly at the 5-character minimum"""
    payload = {
        "name": "Music Society",
        "description": "Hello",
        "category": "Arts",
        "type": "UNOFFICIAL"
    }
    response = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
 
 
@pytest.mark.asyncio
async def test_create_club_description_below_min_length_fails(client, student_token):
    """Validate that club creation is rejected when the description is below the 5-character minimum"""
    payload = {
        "name": "Music Society",
        "description": "Hi",
        "category": "Arts",
        "type": "UNOFFICIAL"
    }
    response = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 422
 
 
@pytest.mark.asyncio
async def test_create_club_description_max_length_boundary_succeeds(client, student_token):
    """Validate that club creation succeeds when the description is exactly at the 1000-character limit"""
    payload = {
        "name": "Debate Club",
        "description": "A" * 1000,
        "category": "Literary",
        "type": "UNOFFICIAL"
    }
    response = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
 
 
@pytest.mark.asyncio
async def test_create_club_description_over_max_length_fails(client, student_token):
    """Validate that club creation is rejected when the description exceeds the 1000-character limit"""
    payload = {
        "name": "Debate Club",
        "description": "A" * 1001,
        "category": "Literary",
        "type": "UNOFFICIAL"
    }
    response = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 422
 
 
@pytest.mark.asyncio
async def test_create_club_category_min_length_boundary_succeeds(client, student_token):
    """Validate that club creation succeeds when the category is exactly at the 2-character minimum"""
    payload = {
        "name": "AI Club",
        "description": "A club focused on artificial intelligence",
        "category": "AI",
        "type": "UNOFFICIAL"
    }
    response = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
 
 
@pytest.mark.asyncio
async def test_create_club_category_below_min_length_fails(client, student_token):
    """Validate that club creation is rejected when the category is below the 2-character minimum"""
    payload = {
        "name": "AI Club",
        "description": "A club focused on artificial intelligence",
        "category": "A",
        "type": "UNOFFICIAL"
    }
    response = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 422
 
 
@pytest.mark.asyncio
async def test_create_club_category_max_length_boundary_succeeds(client, student_token):
    """Validate that club creation succeeds when the category is exactly at the 50-character limit"""
    payload = {
        "name": "Long Category Club",
        "description": "A club with a category at the max length",
        "category": "A" * 50,
        "type": "UNOFFICIAL"
    }
    response = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
 
 
@pytest.mark.asyncio
async def test_create_club_category_over_max_length_fails(client, student_token):
    """Validate that club creation is rejected when the category exceeds the 50-character limit"""
    payload = {
        "name": "Long Category Club",
        "description": "A club with a category exceeding the max length",
        "category": "A" * 51,
        "type": "UNOFFICIAL"
    }
    response = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 422
 
 
@pytest.mark.asyncio
async def test_create_club_invalid_type_fails(client, student_token):
    """Validate that club creation is rejected when the type is not a recognized enum value"""
    payload = {
        "name": "Mystery Club",
        "description": "A club with an invalid type value",
        "category": "Technical",
        "type": "SECRET"
    }
    response = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 422
 
 
@pytest.mark.asyncio
async def test_create_club_missing_required_fields_fails(client, student_token):
    """Validate that club creation is rejected when required fields are missing"""
    payload = {"name": "Incomplete Club"}
    response = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 422
 
 
@pytest.mark.asyncio
async def test_create_club_without_token_fails(client):
    """Verify that club creation is rejected when no authentication token is provided"""
    payload = {
        "name": "No Token Club",
        "description": "A club created without an auth token",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    response = await client.post("/clubs", json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"
 
 
@pytest.mark.asyncio
async def test_create_club_with_admin_token_fails(client, admin_token):
    """Verify that club creation is rejected for a user with the campus admin role"""
    payload = {
        "name": "Admin Attempt Club",
        "description": "A club creation attempt made by an admin",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    response = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 401
    body = response.json()
    assert body["message"] == "Invalid token"
 
 
@pytest.mark.asyncio
async def test_create_club_whitespace_only_name_is_accepted(client, student_token):
    """Confirm that a whitespace-only name currently passes validation since it is not trimmed"""
    payload = {
        "name": "   ",
        "description": "A club created with a blank-looking name",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    response = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    assert response.json()["name"] == "   "
 
 
@pytest.mark.asyncio
async def test_create_club_duplicate_name_is_allowed(client, student_token):
    """Confirm that two clubs with the identical name can both be created since no uniqueness check exists"""
    payload = {
        "name": "Duplicate Club",
        "description": "First club with this exact name",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    first = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
 
    payload = {
        "name": "Duplicate Club",
        "description": "Second club with this exact same name",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    second = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
 
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["name"] == second.json()["name"] == "Duplicate Club"
 
 
@pytest.mark.asyncio
async def test_create_club_accepts_non_url_image_and_link_values(client, student_token):
    """Confirm that image_url and link url values are accepted without any URL-format validation"""
    payload = {
        "name": "Malformed Links Club",
        "description": "A club with garbage image and link urls",
        "category": "Technical",
        "type": "UNOFFICIAL",
        "image_url": "not-a-url",
        "links": [{"label": "Website", "url": "also-not-a-url"}]
    }
    response = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
 
 
@pytest.mark.asyncio
async def test_create_club_link_label_over_max_length_fails(client, student_token):
    """Validate that club creation is rejected when a link label exceeds the 50-character limit"""
    payload = {
        "name": "Long Link Label Club",
        "description": "A club with a link label exceeding the max length",
        "category": "Technical",
        "type": "UNOFFICIAL",
        "links": [{"label": "A" * 51, "url": "https://example.com"}]
    }
    response = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 422
 
 
@pytest.mark.asyncio
async def test_create_club_link_url_over_max_length_fails(client, student_token):
    """Validate that club creation is rejected when a link url exceeds the 500-character limit"""
    payload = {
        "name": "Long Link Url Club",
        "description": "A club with a link url exceeding the max length",
        "category": "Technical",
        "type": "UNOFFICIAL",
        "links": [{"label": "Website", "url": "A" * 501}]
    }
    response = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 422
 
 
# ==== browse ====
 
@pytest.mark.asyncio
async def test_browse_clubs_only_returns_active_clubs_for_students(client, student_token):
    """Verify that students only see ACTIVE clubs when browsing"""
    payload = {
        "name": "Pending Browse Club",
        "description": "A club that stays pending for browse testing",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
 
    payload = {
        "name": "Active Browse Club",
        "description": "A club that is active immediately for browse testing",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
 
    response = await client.get("/clubs", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    names = [club["name"] for club in response.json()]
    assert "Active Browse Club" in names
    assert "Pending Browse Club" not in names
 
 
@pytest.mark.asyncio
async def test_browse_clubs_ignores_status_filter_for_students(client, student_token):
    """Confirm that a student-supplied status filter is ignored and only ACTIVE clubs are returned"""
    payload = {
        "name": "Filtered Pending Club",
        "description": "A pending club used to test the ignored status filter",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
 
    response = await client.get(
        "/clubs", params={"status": "PENDING"}, headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 200
    names = [club["name"] for club in response.json()]
    assert "Filtered Pending Club" not in names
 
 
@pytest.mark.asyncio
async def test_browse_clubs_search_is_case_insensitive(client, student_token):
    """Verify that the search filter matches club names regardless of casing"""
    payload = {
        "name": "Photography Guild",
        "description": "A club for photography enthusiasts",
        "category": "Arts",
        "type": "UNOFFICIAL"
    }
    await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
 
    response = await client.get(
        "/clubs", params={"search": "PHOTOGRAPHY"}, headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 200
    names = [club["name"] for club in response.json()]
    assert "Photography Guild" in names
 
 
@pytest.mark.asyncio
async def test_browse_clubs_category_filter_is_case_insensitive(client, student_token):
    """Verify that the category filter matches regardless of casing"""
    payload = {
        "name": "Painters Circle",
        "description": "A club for painters and sketch artists",
        "category": "Fine Arts",
        "type": "UNOFFICIAL"
    }
    await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
 
    response = await client.get(
        "/clubs", params={"category": "fine arts"}, headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 200
    names = [club["name"] for club in response.json()]
    assert "Painters Circle" in names
 
 
@pytest.mark.asyncio
async def test_browse_clubs_scoped_to_own_college(client, student_token):
    """Verify that clubs from another college are not visible when browsing"""
    admin_payload = {
        "email": "admin@otherbrowse.edu.in",
        "full_name": "Other Browse Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "CAMPUS_ADMIN"
    }
    admin_signup = await client.post("/auth/signup", json=admin_payload)
    other_admin_token = admin_signup.json()["access_token"]
 
    college_payload = {
        "name": "Other Browse College",
        "email_suffix": "otherbrowse.edu.in",
        "description": "A separate college for browse scoping tests"
    }
    await client.post(
        "/college/onboarding", json=college_payload, headers={"Authorization": f"Bearer {other_admin_token}"}
    )
 
    other_student_payload = {
        "email": "leader@otherbrowse.edu.in",
        "full_name": "Other Browse Leader",
        "password": "Leader@123",
        "confirm_password": "Leader@123",
        "role": "STUDENT"
    }
    other_student_signup = await client.post("/auth/signup", json=other_student_payload)
    other_student_token = other_student_signup.json()["access_token"]
 
    club_payload = {
        "name": "Foreign College Club",
        "description": "A club that belongs to a different college",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    await client.post("/clubs", json=club_payload, headers={"Authorization": f"Bearer {other_student_token}"})
 
    response = await client.get("/clubs", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    names = [club["name"] for club in response.json()]
    assert "Foreign College Club" not in names
 
 
@pytest.mark.asyncio
async def test_browse_clubs_without_token_fails(client):
    """Verify that browsing clubs is rejected when no authentication token is provided"""
    response = await client.get("/clubs")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"
 
 
@pytest.mark.asyncio
async def test_browse_clubs_search_below_min_length_fails(client, student_token):
    """Validate that browsing clubs is rejected when the search query is empty"""
    response = await client.get(
        "/clubs", params={"search": ""}, headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 422
 
 
@pytest.mark.asyncio
async def test_browse_clubs_category_over_max_length_fails(client, student_token):
    """Validate that browsing clubs is rejected when the category filter exceeds the 50-character limit"""
    response = await client.get(
        "/clubs", params={"category": "A" * 51}, headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 422
 
 
@pytest.mark.asyncio
async def test_browse_clubs_admin_can_filter_by_status(client, admin_token):
    """Verify that an admin can filter clubs by a specific status"""
    college_payload = {
        "name": "Status Filter College",
        "email_suffix": "newcollege.edu",
        "description": "Onboarding the admin's own college for the status filter test"
    }
    await client.post(
        "/college/onboarding", json=college_payload, headers={"Authorization": f"Bearer {admin_token}"}
    )

    student_payload = {
        "email": "leader@newcollege.edu",
        "full_name": "Status Filter Leader",
        "password": "Leader@123",
        "confirm_password": "Leader@123",
        "role": "STUDENT"
    }
    student_signup = await client.post("/auth/signup", json=student_payload)
    student_token = student_signup.json()["access_token"]

    payload = {
        "name": "Admin Filter Pending Club",
        "description": "A pending club used to test admin status filtering",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})

    response = await client.get(
        "/clubs", params={"status": "PENDING"}, headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    names = [club["name"] for club in response.json()]
    assert "Admin Filter Pending Club" in names
 
 
@pytest.mark.asyncio
async def test_browse_clubs_type_filter_returns_matching_clubs_only(client, student_token):
    """Verify that filtering clubs by type returns only clubs matching that type"""
    payload = {
        "name": "Unofficial Type Filter Club",
        "description": "An unofficial club used to test type filtering",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
 
    response = await client.get(
        "/clubs", params={"type": "UNOFFICIAL"}, headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 200
    types = [club["type"] for club in response.json()]
    assert all(t == "UNOFFICIAL" for t in types)
 
 
@pytest.mark.asyncio
async def test_browse_clubs_type_and_category_combined_filter(client, student_token):
    """Verify that combining type and category filters returns only clubs matching both"""
    payload = {
        "name": "Combined Filter Club",
        "description": "A club used to test combined type and category filtering",
        "category": "Combined Category",
        "type": "UNOFFICIAL"
    }
    await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
 
    response = await client.get(
        "/clubs",
        params={"type": "UNOFFICIAL", "category": "Combined Category"},
        headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 200
    names = [club["name"] for club in response.json()]
    assert "Combined Filter Club" in names
 
 
# ==== view ====
 
@pytest.mark.asyncio
async def test_view_active_club_success_for_student(client, student_token):
    """Verify that a student can view an ACTIVE club's details"""
    payload = {
        "name": "Viewable Club",
        "description": "A club that is active and viewable by students",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]

    response = await client.get(f"/clubs/{club_id}", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == club_id
    assert body["name"] == "Viewable Club"

    assert body["head"] is not None
    assert body["head"]["student_id"] is not None
    assert body["head"]["full_name"] is not None
    assert body["head"]["email"] is None
    assert body["head"]["roll_no"] is None
    assert body["head"]["branch"] is None
    assert body["head"]["year"] is None
 
 
@pytest.mark.asyncio
async def test_view_pending_club_returns_404_even_for_its_own_leader(client, student_token):
    """Confirm that a student cannot view their own PENDING club since only ACTIVE clubs are visible to students"""
    payload = {
        "name": "Own Pending Club",
        "description": "A club left pending to test the leader's own visibility",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    create = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]
 
    response = await client.get(f"/clubs/{club_id}", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Club not found"
 
 
@pytest.mark.asyncio
async def test_view_club_cross_college_returns_404(client, student_token):
    """Verify that viewing a club belonging to a different college returns not found"""
    admin_payload = {
        "email": "admin@otherview.edu.in",
        "full_name": "Other View Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "CAMPUS_ADMIN"
    }
    admin_signup = await client.post("/auth/signup", json=admin_payload)
    other_admin_token = admin_signup.json()["access_token"]
 
    college_payload = {
        "name": "Other View College",
        "email_suffix": "otherview.edu.in",
        "description": "A separate college for view scoping tests"
    }
    await client.post(
        "/college/onboarding", json=college_payload, headers={"Authorization": f"Bearer {other_admin_token}"}
    )
 
    other_student_payload = {
        "email": "leader@otherview.edu.in",
        "full_name": "Other View Leader",
        "password": "Leader@123",
        "confirm_password": "Leader@123",
        "role": "STUDENT"
    }
    other_student_signup = await client.post("/auth/signup", json=other_student_payload)
    other_student_token = other_student_signup.json()["access_token"]
 
    club_payload = {
        "name": "Other College Club",
        "description": "A club that belongs to a different college",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=club_payload, headers={"Authorization": f"Bearer {other_student_token}"})
    club_id = create.json()["id"]
 
    response = await client.get(f"/clubs/{club_id}", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Club not found"
 
 
@pytest.mark.asyncio
async def test_view_nonexistent_club_returns_404(client, student_token):
    """Verify that viewing a nonexistent club id returns not found"""
    response = await client.get("/clubs/999999", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Club not found"
 
 
@pytest.mark.asyncio
async def test_view_pending_club_by_admin_includes_head_info(client):
    """Verify that an admin can view a PENDING club and receives head details"""
    admin_payload = {
        "email": "admin@adminview.edu.in",
        "full_name": "Admin View Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "CAMPUS_ADMIN"
    }
    admin_signup = await client.post("/auth/signup", json=admin_payload)
    admin_token = admin_signup.json()["access_token"]
 
    college_payload = {
        "name": "Admin View College",
        "email_suffix": "adminview.edu.in",
        "description": "A college used to test admin view of pending clubs"
    }
    await client.post(
        "/college/onboarding", json=college_payload, headers={"Authorization": f"Bearer {admin_token}"}
    )
 
    student_payload = {
        "email": "leader@adminview.edu.in",
        "full_name": "Leader Student",
        "password": "Leader@123",
        "confirm_password": "Leader@123",
        "role": "STUDENT"
    }
    student_signup = await client.post("/auth/signup", json=student_payload)
    student_token = student_signup.json()["access_token"]
 
    club_payload = {
        "name": "Admin Visible Club",
        "description": "A pending club that the admin should be able to view",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    create = await client.post("/clubs", json=club_payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]
 
    response = await client.get(f"/clubs/{club_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "PENDING"
    assert body["head"] is not None
    assert body["head"]["full_name"] == "Leader Student"
 
 
@pytest.mark.asyncio
async def test_view_club_without_token_fails(client, student_token):
    """Verify that viewing a club is rejected when no authentication token is provided"""
    payload = {
        "name": "No Token View Club",
        "description": "A club used to test unauthenticated view access",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]
 
    response = await client.get(f"/clubs/{club_id}")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"
 
 
@pytest.mark.asyncio
async def test_view_club_member_count_reflects_approved_members_only(client, student_token):
    """Verify that member_count reflects only approved memberships, not pending ones"""
    payload = {
        "name": "Member Count Club",
        "description": "A club used to test member count accuracy",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]
 
    response = await client.get(f"/clubs/{club_id}", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    assert response.json()["member_count"] == 1
 
 
# ==== update ====
 
@pytest.mark.asyncio
async def test_update_club_success_by_leader(client, student_token):
    """Verify that the club leader can update the club's description and category"""
    payload = {
        "name": "Editable Club",
        "description": "A club that will be edited by its leader",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]
 
    update_payload = {"description": "An updated description here", "category": "Updated Category"}
    response = await client.put(
        f"/clubs/{club_id}", json=update_payload, headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["description"] == "An updated description here"
    assert body["category"] == "Updated Category"
 
 
@pytest.mark.asyncio
async def test_update_club_by_non_leader_fails(client, student_token):
    """Verify that a student who is not the club leader cannot update the club"""
    payload = {
        "name": "Leader Only Club",
        "description": "A club that only its leader can edit",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]
 
    other_payload = {
        "email": "second.member@knit.edu.in",
        "full_name": "Second Member",
        "password": "Member@123",
        "confirm_password": "Member@123",
        "role": "STUDENT"
    }
    other_signup = await client.post("/auth/signup", json=other_payload)
    other_token = other_signup.json()["access_token"]
 
    update_payload = {"description": "Trying to edit as non-leader"}
    response = await client.put(
        f"/clubs/{club_id}", json=update_payload, headers={"Authorization": f"Bearer {other_token}"}
    )
    assert response.status_code == 403
    body = response.json()
    assert body["message"] == "Only the club leader can perform this action"
 
 
@pytest.mark.asyncio
async def test_update_club_immutable_fields_are_ignored(client, student_token):
    """Confirm that name and type fields are silently ignored on update since the schema does not accept them"""
    payload = {
        "name": "Immutable Name Club",
        "description": "A club used to test immutable field handling",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]
 
    update_payload = {"name": "Renamed Club", "type": "OFFICIAL", "description": "Only this should change"}
    response = await client.put(
        f"/clubs/{club_id}", json=update_payload, headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Immutable Name Club"
    assert body["type"] == "UNOFFICIAL"
    assert body["description"] == "Only this should change"
 
 
@pytest.mark.asyncio
async def test_update_nonexistent_club_returns_404(client, student_token):
    """Verify that updating a nonexistent club id returns not found"""
    update_payload = {"description": "Does not matter"}
    response = await client.put(
        "/clubs/999999", json=update_payload, headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Club not found"
 
 
@pytest.mark.asyncio
async def test_update_club_description_min_length_boundary_succeeds(client, student_token):
    """Validate that club update succeeds when description is exactly at the 5-character minimum"""
    payload = {
        "name": "Update Min Desc Club",
        "description": "A club used to test the update description minimum boundary",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]
 
    update_payload = {"description": "Hello"}
    response = await client.put(
        f"/clubs/{club_id}", json=update_payload, headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 200
    assert response.json()["description"] == "Hello"
 
 
@pytest.mark.asyncio
async def test_update_club_description_below_min_length_fails(client, student_token):
    """Validate that club update is rejected when description is below the 5-character minimum"""
    payload = {
        "name": "Update Short Desc Club",
        "description": "A club used to test rejection of too-short update descriptions",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]
 
    update_payload = {"description": "Hi"}
    response = await client.put(
        f"/clubs/{club_id}", json=update_payload, headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 422
 
 
@pytest.mark.asyncio
async def test_update_club_description_over_max_length_fails(client, student_token):
    """Validate that club update is rejected when description exceeds the 1000-character limit"""
    payload = {
        "name": "Update Long Desc Club",
        "description": "A club used to test rejection of too-long update descriptions",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]
 
    update_payload = {"description": "A" * 1001}
    response = await client.put(
        f"/clubs/{club_id}", json=update_payload, headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 422
 
 
@pytest.mark.asyncio
async def test_update_club_category_max_length_boundary_succeeds(client, student_token):
    """Validate that club update succeeds when category is exactly at the 50-character limit"""
    payload = {
        "name": "Update Max Category Club",
        "description": "A club used to test the update category maximum boundary",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]
 
    update_payload = {"category": "A" * 50}
    response = await client.put(
        f"/clubs/{club_id}", json=update_payload, headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 200
    assert response.json()["category"] == "A" * 50
 
 
@pytest.mark.asyncio
async def test_update_club_category_below_min_length_fails(client, student_token):
    """Validate that club update is rejected when category is below the 2-character minimum"""
    payload = {
        "name": "Update Short Category Club",
        "description": "A club used to test rejection of too-short update categories",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]
 
    update_payload = {"category": "A"}
    response = await client.put(
        f"/clubs/{club_id}", json=update_payload, headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 422
 
 
@pytest.mark.asyncio
async def test_update_club_link_label_over_max_length_fails(client, student_token):
    """Validate that club update is rejected when a link label exceeds the 50-character limit"""
    payload = {
        "name": "Update Link Label Club",
        "description": "A club used to test rejection of too-long update link labels",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]
 
    update_payload = {"links": [{"label": "A" * 51, "url": "https://example.com"}]}
    response = await client.put(
        f"/clubs/{club_id}", json=update_payload, headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 422
 
 
@pytest.mark.asyncio
async def test_update_club_link_url_over_max_length_fails(client, student_token):
    """Validate that club update is rejected when a link url exceeds the 500-character limit"""
    payload = {
        "name": "Update Link Url Club",
        "description": "A club used to test rejection of too-long update link urls",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]
 
    update_payload = {"links": [{"label": "Website", "url": "A" * 501}]}
    response = await client.put(
        f"/clubs/{club_id}", json=update_payload, headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 422
 
@pytest.mark.asyncio
async def test_update_club_links_replaced_successfully(client, db_session, student_token):
    """Verify that updating a club's links replaces the existing set of links"""
    payload = {
        "name": "Link Replace Club",
        "description": "A club used to test link replacement on update",
        "category": "Technical",
        "type": "UNOFFICIAL",
        "links": [{"label": "Old Site", "url": "https://old.example.com"}]
    }
    create = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]

    update_payload = {"links": [{"label": "New Site", "url": "https://new.example.com"}]}
    response = await client.put(
        f"/clubs/{club_id}", json=update_payload, headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    labels = [link["label"] for link in body["links"]]
    # the PUT response itself returns stale links right after
    # the real check is the GET below.

    db_session.expire_all()

    get_response = await client.get(
        f"/clubs/{club_id}", headers={"Authorization": f"Bearer {student_token}"}
    )
    assert get_response.status_code == 200
    get_labels = [link["label"] for link in get_response.json()["links"]]
    assert get_labels == ["New Site"]

# @pytest.mark.asyncio
# async def test_update_club_links_replaced_successfully(client, student_token):
#     """Verify that updating a club's links replaces the existing set of links"""
#     payload = {
#         "name": "Link Replace Club",
#         "description": "A club used to test link replacement on update",
#         "category": "Technical",
#         "type": "UNOFFICIAL",
#         "links": [{"label": "Old Site", "url": "https://old.example.com"}]
#     }
#     create = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
#     club_id = create.json()["id"]

#     update_payload = {"links": [{"label": "New Site", "url": "https://new.example.com"}]}
#     response = await client.put(
#         f"/clubs/{club_id}", json=update_payload, headers={"Authorization": f"Bearer {student_token}"}
#     )
#     assert response.status_code == 200
#     body = response.json()
#     put_labels = [link["label"] for link in body["links"]]

#     get_response = await client.get(
#         f"/clubs/{club_id}", headers={"Authorization": f"Bearer {student_token}"}
#     )
#     assert get_response.status_code == 200
#     get_labels = [link["label"] for link in get_response.json()["links"]]

#     print(f"PUT response labels: {put_labels}")
#     print(f"GET response labels: {get_labels}")

#     assert put_labels == ["New Site"], f"PUT response stale: {put_labels}"
#     assert get_labels == ["New Site"], f"GET response stale: {get_labels}"


@pytest.mark.asyncio
async def test_update_club_links_empty_list_clears_links(client, db_session, student_token):
    """Verify that passing an empty links list removes all existing links"""
    payload = {
        "name": "Link Clear Club",
        "description": "A club used to test clearing links on update",
        "category": "Technical",
        "type": "UNOFFICIAL",
        "links": [{"label": "Old Site", "url": "https://old.example.com"}]
    }
    create = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]

    update_payload = {"links": []}
    response = await client.put(
        f"/clubs/{club_id}", json=update_payload, headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 200
    # PUT response itself returns stale links right after
    # saving, even though the database write is correct.

    db_session.expire_all()

    get_response = await client.get(
        f"/clubs/{club_id}", headers={"Authorization": f"Bearer {student_token}"}
    )
    assert get_response.status_code == 200
    assert get_response.json()["links"] == []
 
 
@pytest.mark.asyncio
async def test_update_club_links_omitted_leaves_existing_links_unchanged(client, student_token):
    """Confirm that omitting the links field leaves existing links unchanged"""
    payload = {
        "name": "Link Untouched Club",
        "description": "A club used to test that omitted links are left unchanged",
        "category": "Technical",
        "type": "UNOFFICIAL",
        "links": [{"label": "Kept Site", "url": "https://kept.example.com"}]
    }
    create = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]
 
    update_payload = {"description": "Only description should change here"}
    response = await client.put(
        f"/clubs/{club_id}", json=update_payload, headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    labels = [link["label"] for link in body["links"]]
    assert labels == ["Kept Site"]
 
 
@pytest.mark.asyncio
async def test_update_club_image_url_success(client, student_token):
    """Verify that a club's image_url can be updated by its leader"""
    payload = {
        "name": "Image Update Club",
        "description": "A club used to test image_url updates",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]
 
    update_payload = {"image_url": "https://example.com/new-image.png"}
    response = await client.put(
        f"/clubs/{club_id}", json=update_payload, headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 200
    assert response.json()["image_url"] == "https://example.com/new-image.png"

@pytest.mark.asyncio
async def test_update_club_with_no_fields_provided_is_a_noop(client, student_token):
    """Confirm that updating a club with an empty payload leaves all fields unchanged"""
    payload = {
        "name": "Noop Update Club",
        "description": "A club used to test empty payload updates",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]
 
    response = await client.put(
        f"/clubs/{club_id}", json={}, headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["description"] == "A club used to test empty payload updates"
    assert body["category"] == "Technical"
 
 
@pytest.mark.asyncio
async def test_update_club_without_token_fails(client, student_token):
    """Verify that club update is rejected when no authentication token is provided"""
    payload = {
        "name": "No Token Update Club",
        "description": "A club used to test unauthenticated update access",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]
 
    update_payload = {"description": "Should not be applied"}
    response = await client.put(f"/clubs/{club_id}", json=update_payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"
 
 
@pytest.mark.asyncio
async def test_update_nonexistent_club_by_non_leader_returns_404_not_403(client, student_token):
    """Confirm that updating a nonexistent club returns not found before the leader check runs"""
    update_payload = {"description": "Does not matter here"}
    response = await client.put(
        "/clubs/999999", json=update_payload, headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Club not found"
 
 
# ==== delete ====
 
@pytest.mark.asyncio
async def test_delete_club_by_leader_success(client, student_token):
    """Verify that the club leader can archive the club"""
    payload = {
        "name": "Deletable Club",
        "description": "A club that will be archived by its leader",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]
 
    response = await client.delete(f"/clubs/{club_id}", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ARCHIVED"
    assert body["message"] == "Club archived successfully"
 
 
@pytest.mark.asyncio
async def test_delete_club_by_non_leader_fails(client, student_token):
    """Verify that a student who is not the club leader cannot archive the club"""
    payload = {
        "name": "Protected Club",
        "description": "A club that only its leader can archive",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]
 
    other_payload = {
        "email": "third.member@knit.edu.in",
        "full_name": "Third Member",
        "password": "Member@123",
        "confirm_password": "Member@123",
        "role": "STUDENT"
    }
    other_signup = await client.post("/auth/signup", json=other_payload)
    other_token = other_signup.json()["access_token"]
 
    response = await client.delete(f"/clubs/{club_id}", headers={"Authorization": f"Bearer {other_token}"})
    assert response.status_code == 403
    body = response.json()
    assert body["message"] == "Only the club leader can perform this action"
 
 
@pytest.mark.asyncio
async def test_delete_already_archived_club_is_idempotent(client, student_token):
    """Confirm that archiving an already-archived club succeeds again since no status guard exists"""
    payload = {
        "name": "Twice Archived Club",
        "description": "A club that will be archived more than once",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]
 
    await client.delete(f"/clubs/{club_id}", headers={"Authorization": f"Bearer {student_token}"})
    response = await client.delete(f"/clubs/{club_id}", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ARCHIVED"
 
 
@pytest.mark.asyncio
async def test_delete_nonexistent_club_returns_404(client, student_token):
    """Verify that archiving a nonexistent club id returns not found"""
    response = await client.delete("/clubs/999999", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Club not found"
 
 
@pytest.mark.asyncio
async def test_delete_club_without_token_fails(client, student_token):
    """Verify that club archival is rejected when no authentication token is provided"""
    payload = {
        "name": "No Token Delete Club",
        "description": "A club used to test unauthenticated delete access",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]
 
    response = await client.delete(f"/clubs/{club_id}")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"
 
 
# ==== approve / reject ====
 
@pytest.mark.asyncio
async def test_approve_pending_club_success(client):
    """Verify that an admin can approve a PENDING club belonging to their own college"""
    admin_payload = {
        "email": "admin@approve.edu.in",
        "full_name": "Approve Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "CAMPUS_ADMIN"
    }
    admin_signup = await client.post("/auth/signup", json=admin_payload)
    admin_token = admin_signup.json()["access_token"]
 
    college_payload = {
        "name": "Approve College",
        "email_suffix": "approve.edu.in",
        "description": "A college used to test club approval"
    }
    await client.post(
        "/college/onboarding", json=college_payload, headers={"Authorization": f"Bearer {admin_token}"}
    )
 
    student_payload = {
        "email": "leader@approve.edu.in",
        "full_name": "Approve Leader",
        "password": "Leader@123",
        "confirm_password": "Leader@123",
        "role": "STUDENT"
    }
    student_signup = await client.post("/auth/signup", json=student_payload)
    student_token = student_signup.json()["access_token"]
 
    club_payload = {
        "name": "Approvable Club",
        "description": "A pending club awaiting admin approval",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    create = await client.post("/clubs", json=club_payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]
 
    response = await client.patch(f"/clubs/{club_id}/approve", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ACTIVE"
    assert body["message"] == "Club approved"
 
 
@pytest.mark.asyncio
async def test_reject_pending_club_success(client):
    """Verify that an admin can reject a PENDING club belonging to their own college"""
    admin_payload = {
        "email": "admin@reject.edu.in",
        "full_name": "Reject Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "CAMPUS_ADMIN"
    }
    admin_signup = await client.post("/auth/signup", json=admin_payload)
    admin_token = admin_signup.json()["access_token"]
 
    college_payload = {
        "name": "Reject College",
        "email_suffix": "reject.edu.in",
        "description": "A college used to test club rejection"
    }
    await client.post(
        "/college/onboarding", json=college_payload, headers={"Authorization": f"Bearer {admin_token}"}
    )
 
    student_payload = {
        "email": "leader@reject.edu.in",
        "full_name": "Reject Leader",
        "password": "Leader@123",
        "confirm_password": "Leader@123",
        "role": "STUDENT"
    }
    student_signup = await client.post("/auth/signup", json=student_payload)
    student_token = student_signup.json()["access_token"]
 
    club_payload = {
        "name": "Rejectable Club",
        "description": "A pending club awaiting admin rejection",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    create = await client.post("/clubs", json=club_payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]
 
    response = await client.patch(f"/clubs/{club_id}/reject", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "REJECTED"
    assert body["message"] == "Club rejected"
 
 
@pytest.mark.asyncio
async def test_approve_club_by_student_fails(client, student_token):
    """Verify that a student cannot approve a club"""
    payload = {
        "name": "Student Approve Attempt",
        "description": "A club approval attempt made by a student",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    create = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]
 
    response = await client.patch(f"/clubs/{club_id}/approve", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 401
    body = response.json()
    assert body["message"] == "Invalid token"
 
 
@pytest.mark.asyncio
async def test_approve_already_active_club_fails(client):
    """Confirm that approving a club that is already ACTIVE is rejected as not pending"""
    admin_payload = {
        "email": "admin@doubleapprove.edu.in.in",
        "full_name": "Double Approve Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "CAMPUS_ADMIN"
    }
    admin_signup = await client.post("/auth/signup", json=admin_payload)
    admin_token = admin_signup.json()["access_token"]
 
    college_payload = {
        "name": "Double Approve College",
        "email_suffix": "doubleapprove.edu.in.in",
        "description": "A college used to test double approval rejection"
    }
    await client.post(
        "/college/onboarding", json=college_payload, headers={"Authorization": f"Bearer {admin_token}"}
    )
 
    student_payload = {
        "email": "leader@doubleapprove.edu.in.in",
        "full_name": "Double Approve Leader",
        "password": "Leader@123",
        "confirm_password": "Leader@123",
        "role": "STUDENT"
    }
    student_signup = await client.post("/auth/signup", json=student_payload)
    student_token = student_signup.json()["access_token"]
 
    club_payload = {
        "name": "Already Active Club",
        "description": "A club that is already active before approval is attempted",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=club_payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]
 
    response = await client.patch(f"/clubs/{club_id}/approve", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 403
    body = response.json()
    assert body["message"] == "Club is not pending approval"
 
 
@pytest.mark.asyncio
async def test_approve_club_from_different_college_fails(client):
    """Verify that an admin cannot approve a club belonging to a different college"""
    owner_admin_payload = {
        "email": "admin@clubowner.edu.in",
        "full_name": "Club Owner Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "CAMPUS_ADMIN"
    }
    owner_admin_signup = await client.post("/auth/signup", json=owner_admin_payload)
    owner_admin_token = owner_admin_signup.json()["access_token"]
 
    owner_college_payload = {
        "name": "Club Owner College",
        "email_suffix": "clubowner.edu.in",
        "description": "A college that owns the club under test"
    }
    await client.post(
        "/college/onboarding", json=owner_college_payload, headers={"Authorization": f"Bearer {owner_admin_token}"}
    )
 
    owner_student_payload = {
        "email": "leader@clubowner.edu.in",
        "full_name": "Club Owner Leader",
        "password": "Leader@123",
        "confirm_password": "Leader@123",
        "role": "STUDENT"
    }
    owner_student_signup = await client.post("/auth/signup", json=owner_student_payload)
    owner_student_token = owner_student_signup.json()["access_token"]
 
    other_admin_payload = {
        "email": "admin@otheradmin.edu.in",
        "full_name": "Other Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "CAMPUS_ADMIN"
    }
    other_admin_signup = await client.post("/auth/signup", json=other_admin_payload)
    other_admin_token = other_admin_signup.json()["access_token"]
 
    other_college_payload = {
        "name": "Other Admin College",
        "email_suffix": "otheradmin.edu.in",
        "description": "A different college whose admin should not approve"
    }
    await client.post(
        "/college/onboarding", json=other_college_payload, headers={"Authorization": f"Bearer {other_admin_token}"}
    )
 
    club_payload = {
        "name": "Cross College Club",
        "description": "A club that belongs to a different college than the approving admin",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    create = await client.post(
        "/clubs", json=club_payload, headers={"Authorization": f"Bearer {owner_student_token}"}
    )
    club_id = create.json()["id"]
 
    response = await client.patch(
        f"/clubs/{club_id}/approve", headers={"Authorization": f"Bearer {other_admin_token}"}
    )
    assert response.status_code == 403
    body = response.json()
    assert body["message"] == "This action is not allowed"
 
 
@pytest.mark.asyncio
async def test_reject_already_rejected_club_fails(client):
    """Confirm that rejecting a club that is already REJECTED is rejected as not pending"""
    admin_payload = {
        "email": "admin@doublereject.edu.in.in",
        "full_name": "Double Reject Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "CAMPUS_ADMIN"
    }
    admin_signup = await client.post("/auth/signup", json=admin_payload)
    admin_token = admin_signup.json()["access_token"]
 
    college_payload = {
        "name": "Double Reject College",
        "email_suffix": "doublereject.edu.in.in",
        "description": "A college used to test double rejection"
    }
    await client.post(
        "/college/onboarding", json=college_payload, headers={"Authorization": f"Bearer {admin_token}"}
    )
 
    student_payload = {
        "email": "leader@doublereject.edu.in.in",
        "full_name": "Double Reject Leader",
        "password": "Leader@123",
        "confirm_password": "Leader@123",
        "role": "STUDENT"
    }
    student_signup = await client.post("/auth/signup", json=student_payload)
    student_token = student_signup.json()["access_token"]
 
    club_payload = {
        "name": "Already Rejected Club",
        "description": "A club that will be rejected more than once",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    create = await client.post("/clubs", json=club_payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]
 
    await client.patch(f"/clubs/{club_id}/reject", headers={"Authorization": f"Bearer {admin_token}"})
    response = await client.patch(f"/clubs/{club_id}/reject", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 403
    body = response.json()
    assert body["message"] == "Club is not pending approval"
 
 
@pytest.mark.asyncio
async def test_approve_nonexistent_club_returns_404(client, admin_token):
    """Verify that approving a nonexistent club id returns not found"""
    response = await client.patch("/clubs/999999/approve", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Club not found"
 
 
@pytest.mark.asyncio
async def test_reject_club_by_student_fails(client, student_token):
    """Verify that a student cannot reject a club"""
    payload = {
        "name": "Student Reject Attempt",
        "description": "A club rejection attempt made by a student",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    create = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]
 
    response = await client.patch(f"/clubs/{club_id}/reject", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 401
    body = response.json()
    assert body["message"] == "Invalid token"
 
 
@pytest.mark.asyncio
async def test_reject_club_from_different_college_fails(client):
    """Verify that an admin cannot reject a club belonging to a different college"""
    owner_admin_payload = {
        "email": "admin@rejectowner.edu.in",
        "full_name": "Reject Owner Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "CAMPUS_ADMIN"
    }
    owner_admin_signup = await client.post("/auth/signup", json=owner_admin_payload)
    owner_admin_token = owner_admin_signup.json()["access_token"]
 
    owner_college_payload = {
        "name": "Reject Owner College",
        "email_suffix": "rejectowner.edu.in",
        "description": "A college that owns the club under test for reject scoping"
    }
    await client.post(
        "/college/onboarding", json=owner_college_payload, headers={"Authorization": f"Bearer {owner_admin_token}"}
    )
 
    owner_student_payload = {
        "email": "leader@rejectowner.edu.in",
        "full_name": "Reject Owner Leader",
        "password": "Leader@123",
        "confirm_password": "Leader@123",
        "role": "STUDENT"
    }
    owner_student_signup = await client.post("/auth/signup", json=owner_student_payload)
    owner_student_token = owner_student_signup.json()["access_token"]
 
    other_admin_payload = {
        "email": "admin@rejectother.edu.in",
        "full_name": "Reject Other Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "CAMPUS_ADMIN"
    }
    other_admin_signup = await client.post("/auth/signup", json=other_admin_payload)
    other_admin_token = other_admin_signup.json()["access_token"]
 
    other_college_payload = {
        "name": "Reject Other College",
        "email_suffix": "rejectother.edu.in",
        "description": "A different college whose admin should not reject"
    }
    await client.post(
        "/college/onboarding", json=other_college_payload, headers={"Authorization": f"Bearer {other_admin_token}"}
    )
 
    club_payload = {
        "name": "Cross College Reject Club",
        "description": "A club that belongs to a different college than the rejecting admin",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    create = await client.post(
        "/clubs", json=club_payload, headers={"Authorization": f"Bearer {owner_student_token}"}
    )
    club_id = create.json()["id"]
 
    response = await client.patch(
        f"/clubs/{club_id}/reject", headers={"Authorization": f"Bearer {other_admin_token}"}
    )
    assert response.status_code == 403
    body = response.json()
    assert body["message"] == "This action is not allowed"
 
 
@pytest.mark.asyncio
async def test_reject_nonexistent_club_returns_404(client, admin_token):
    """Verify that rejecting a nonexistent club id returns not found"""
    response = await client.patch("/clubs/999999/reject", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Club not found"
 
 
@pytest.mark.asyncio
async def test_approve_club_without_token_fails(client, student_token):
    """Verify that club approval is rejected when no authentication token is provided"""
    payload = {
        "name": "No Token Approve Club",
        "description": "A club used to test unauthenticated approve access",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    create = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]
 
    response = await client.patch(f"/clubs/{club_id}/approve")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"

# ==== my clubs ====

@pytest.mark.asyncio
async def test_my_clubs_role_leader_returns_led_clubs(client, student_token):
    """Verify that role=LEADER returns clubs the student leads"""
    payload = {
        "name": "My Led Club",
        "description": "A club led by the requesting student",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})

    response = await client.get(
        "/clubs/me", params={"role": "LEADER"}, headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    names = [item["name"] for item in body]
    assert "My Led Club" in names
    assert all(item["membership_role"] == "LEADER" for item in body)


@pytest.mark.asyncio
async def test_my_clubs_role_leader_with_status_filters_club_status(client, student_token):
    """Verify that role=LEADER with status filters by the club's approval status"""
    payload = {
        "name": "Active Led Club",
        "description": "An active club led by the student",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})

    payload = {
        "name": "Pending Led Club",
        "description": "A pending club led by the student",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})

    response = await client.get(
        "/clubs/me",
        params={"role": "LEADER", "status": "ACTIVE"},
        headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert "Active Led Club" in names
    assert "Pending Led Club" not in names


@pytest.mark.asyncio
async def test_my_clubs_role_member_returns_joined_clubs(client, student_token):
    """Verify that role=MEMBER returns clubs the student has joined"""
    payload = {
        "name": "Joinable Member Club",
        "description": "A club the student will join as a member",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]

    payload = {
        "email": "myclubs.joiner@knit.edu.in",
        "full_name": "MyClubs Joiner",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "STUDENT"
    }
    joiner_signup = await client.post("/auth/signup", json=payload)
    joiner_token = joiner_signup.json()["access_token"]
    await client.post(f"/clubs/{club_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})

    response = await client.get(
        "/clubs/me", params={"role": "MEMBER"}, headers={"Authorization": f"Bearer {joiner_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    names = [item["name"] for item in body]
    assert "Joinable Member Club" in names
    assert all(item["membership_role"] == "MEMBER" for item in body)


@pytest.mark.asyncio
async def test_my_clubs_role_member_with_status_filters_membership_status(client, student_token):
    """Verify that role=MEMBER with status filters by the membership's own status, not club status"""
    payload = {
        "name": "Membership Status Club",
        "description": "A club used to test membership status filtering",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    create = await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    club_id = create.json()["id"]

    payload = {
        "email": "myclubs.pendingjoiner@knit.edu.in",
        "full_name": "MyClubs Pending Joiner",
        "password": "Joiner@123",
        "confirm_password": "Joiner@123",
        "role": "STUDENT"
    }
    joiner_signup = await client.post("/auth/signup", json=payload)
    joiner_token = joiner_signup.json()["access_token"]
    await client.post(f"/clubs/{club_id}/join", headers={"Authorization": f"Bearer {joiner_token}"})

    response = await client.get(
        "/clubs/me",
        params={"role": "MEMBER", "status": "PENDING"},
        headers={"Authorization": f"Bearer {joiner_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    names = [item["name"] for item in body]
    assert "Membership Status Club" in names
    assert all(item["membership_status"] == "PENDING" for item in body)


@pytest.mark.asyncio
async def test_my_clubs_status_without_role_fails(client, student_token):
    """Validate that supplying status without role is rejected"""
    response = await client.get(
        "/clubs/me", params={"status": "ACTIVE"}, headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 422
    body = response.json()
    assert body["message"] == (
        "status must be sent together with role: it means the club status for LEADER "
        "and your membership status for MEMBER"
    )


@pytest.mark.asyncio
async def test_my_clubs_leader_status_with_membership_status_value_fails(client, student_token):
    """Validate that role=LEADER with a membership-status value (not a club status) is rejected"""
    response = await client.get(
        "/clubs/me",
        params={"role": "LEADER", "status": "APPROVED"},
        headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 422
    body = response.json()
    assert "status must be one of" in body["message"]
    assert "role is LEADER" in body["message"]


@pytest.mark.asyncio
async def test_my_clubs_member_status_with_club_status_value_fails(client, student_token):
    """Validate that role=MEMBER with a club-status value (not a membership status) is rejected"""
    response = await client.get(
        "/clubs/me",
        params={"role": "MEMBER", "status": "ARCHIVED"},
        headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 422
    body = response.json()
    assert "status must be one of" in body["message"]
    assert "role is MEMBER" in body["message"]


@pytest.mark.asyncio
async def test_my_clubs_invalid_role_value_fails(client, student_token):
    """Validate that an unrecognized role value is rejected"""
    response = await client.get(
        "/clubs/me", params={"role": "PRESIDENT"}, headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_my_clubs_no_role_no_status_returns_all(client, student_token):
    """Verify that omitting both role and status returns all of the student's clubs regardless of role"""
    payload = {
        "name": "No Filter Club",
        "description": "A club used to test the unfiltered my-clubs listing",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})

    response = await client.get("/clubs/me", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert "No Filter Club" in names


@pytest.mark.asyncio
async def test_my_clubs_includes_head_name_and_member_count(client, student_token):
    """Verify that each item includes head_name and member_count"""
    payload = {
        "name": "Head Name Club",
        "description": "A club used to test head_name and member_count fields",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})

    response = await client.get("/clubs/me", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    item = next(i for i in response.json() if i["name"] == "Head Name Club")
    assert item["head_name"] == "Club Student"
    assert item["member_count"] == 1


# @pytest.mark.asyncio
# async def test_my_clubs_ordered_by_most_recent_membership_first(client, student_token):
#     """Verify that results are ordered by membership created_at descending, most recent first"""
#     payload = {
#         "name": "First Created Club",
#         "description": "The first club the student joins/creates",
#         "category": "Technical",
#         "type": "UNOFFICIAL"
#     }
#     await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})

#     payload = {
#         "name": "Second Created Club",
#         "description": "The second club the student joins/creates",
#         "category": "Technical",
#         "type": "UNOFFICIAL"
#     }
#     await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})

#     response = await client.get("/clubs/me", headers={"Authorization": f"Bearer {student_token}"})
    
#     assert response.status_code == 200
#     names = [item["name"] for item in response.json()]
#     assert names.index("Second Created Club") < names.index("First Created Club")


@pytest.mark.asyncio
async def test_my_clubs_empty_for_student_with_no_clubs(client, seed_college):
    """Verify that a student with no memberships gets an empty list"""
    payload = {
        "email": "noclubs.student@knit.edu.in",
        "full_name": "No Clubs Student",
        "password": "Student@123",
        "confirm_password": "Student@123",
        "role": "STUDENT"
    }
    signup = await client.post("/auth/signup", json=payload)
    token = signup.json()["access_token"]

    response = await client.get("/clubs/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_my_clubs_without_token_fails(client):
    """Verify that requesting my-clubs is rejected when no authentication token is provided"""
    response = await client.get("/clubs/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"
