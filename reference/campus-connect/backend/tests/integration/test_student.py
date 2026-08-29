
import pytest


# ==== me (get own profile) ====

@pytest.mark.asyncio
async def test_get_my_profile_success(client, student_token):
    """Verify that a student can fetch their own profile with all expected fields"""
    response = await client.get("/students/me", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Club Student"
    assert body["email"] == "club.student@knit.edu.in"
    assert body["bio"] is None
    assert body["interests"] == []
    assert body["roll_no"] is None
    assert body["branch"] is None
    assert body["year"] is None
    assert body["joined_clubs"] == []
    assert "student_id" in body
    assert "created_at" in body


@pytest.mark.asyncio
async def test_get_my_profile_without_token_fails(client):
    """Verify that fetching own profile is rejected when no authentication token is provided"""
    response = await client.get("/students/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.asyncio
async def test_get_my_profile_with_admin_token_fails(client, admin_token):
    """Verify that fetching own profile is rejected for a user with the campus admin role"""
    response = await client.get("/students/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 401
    body = response.json()
    assert body["message"] == "Invalid token"


@pytest.mark.asyncio
async def test_get_my_profile_joined_clubs_only_includes_approved_active_memberships(client, student_token):
    """Verify that joined_clubs only lists clubs where membership is APPROVED and the club is ACTIVE"""
    payload = {
        "name": "Own Club Membership",
        "description": "A club the student leads and is auto-approved into",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})

    response = await client.get("/students/me", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    body = response.json()
    club_names = [c["name"] for c in body["joined_clubs"]]
    assert "Own Club Membership" in club_names


@pytest.mark.asyncio
async def test_get_my_profile_joined_clubs_excludes_pending_official_club(client, student_token):
    """Confirm that a PENDING (not yet approved) official club is not listed in joined_clubs"""
    payload = {
        "name": "Pending Membership Club",
        "description": "An official club that stays pending admin approval",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})

    response = await client.get("/students/me", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    club_names = [c["name"] for c in response.json()["joined_clubs"]]
    assert "Pending Membership Club" not in club_names


# ==== me (update own profile) ====

@pytest.mark.asyncio
async def test_update_my_profile_success_all_fields(client, student_token):
    """Verify that updating all profile fields at once succeeds and returns the confirmation message"""
    payload = {
        "bio": "I love robotics and chess",
        "interests": ["Robotics", "Chess"],
        "roll_no": "CS2024001",
        "branch": "Computer Science",
        "year": 2
    }
    response = await client.patch("/students/me", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["bio"] == "I love robotics and chess"
    assert body["interests"] == ["Robotics", "Chess"]
    assert body["roll_no"] == "CS2024001"
    assert body["branch"] == "Computer Science"
    assert body["year"] == 2
    assert body["message"] == "Profile updated successfully"


@pytest.mark.asyncio
async def test_update_my_profile_partial_update_leaves_other_fields_unchanged(client, student_token):
    """Verify that updating only one field leaves previously set fields untouched"""
    first_payload = {"bio": "Initial bio", "branch": "Electronics", "year": 1}
    await client.patch("/students/me", json=first_payload, headers={"Authorization": f"Bearer {student_token}"})

    second_payload = {"bio": "Updated bio only"}
    response = await client.patch(
        "/students/me", json=second_payload, headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["bio"] == "Updated bio only"
    assert body["branch"] == "Electronics"
    assert body["year"] == 1


@pytest.mark.asyncio
async def test_update_my_profile_empty_payload_is_a_noop(client, student_token):
    """Confirm that updating with an empty payload leaves all fields unchanged"""
    payload = {"bio": "Untouched bio", "branch": "Mechanical", "year": 3}
    await client.patch("/students/me", json=payload, headers={"Authorization": f"Bearer {student_token}"})

    response = await client.patch("/students/me", json={}, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["bio"] == "Untouched bio"
    assert body["branch"] == "Mechanical"
    assert body["year"] == 3


@pytest.mark.asyncio
async def test_update_my_profile_bio_max_length_boundary_succeeds(client, student_token):
    """Validate that profile update succeeds when bio is exactly at the 500-character limit"""
    payload = {"bio": "A" * 500}
    response = await client.patch("/students/me", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    assert response.json()["bio"] == "A" * 500


@pytest.mark.asyncio
async def test_update_my_profile_bio_over_max_length_fails(client, student_token):
    """Validate that profile update is rejected when bio exceeds the 500-character limit"""
    payload = {"bio": "A" * 501}
    response = await client.patch("/students/me", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_my_profile_bio_blank_string_coerced_to_none(client, student_token):
    """Confirm that a whitespace-only bio is coerced to None instead of being stored literally"""
    await client.patch("/students/me", json={"bio": "Some bio"}, headers={"Authorization": f"Bearer {student_token}"})

    response = await client.patch(
        "/students/me", json={"bio": "   "}, headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 200
    assert response.json()["bio"] is None


@pytest.mark.asyncio
async def test_update_my_profile_roll_no_max_length_boundary_succeeds(client, student_token):
    """Validate that profile update succeeds when roll_no is exactly at the 50-character limit"""
    payload = {"roll_no": "A" * 50}
    response = await client.patch("/students/me", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    assert response.json()["roll_no"] == "A" * 50


@pytest.mark.asyncio
async def test_update_my_profile_roll_no_over_max_length_fails(client, student_token):
    """Validate that profile update is rejected when roll_no exceeds the 50-character limit"""
    payload = {"roll_no": "A" * 51}
    response = await client.patch("/students/me", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_my_profile_roll_no_blank_string_coerced_to_none(client, student_token):
    """Confirm that a blank roll_no is coerced to None"""
    response = await client.patch(
        "/students/me", json={"roll_no": "  "}, headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 200
    assert response.json()["roll_no"] is None


@pytest.mark.asyncio
async def test_update_my_profile_branch_max_length_boundary_succeeds(client, student_token):
    """Validate that profile update succeeds when branch is exactly at the 100-character limit"""
    payload = {"branch": "A" * 100}
    response = await client.patch("/students/me", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    assert response.json()["branch"] == "A" * 100


@pytest.mark.asyncio
async def test_update_my_profile_branch_over_max_length_fails(client, student_token):
    """Validate that profile update is rejected when branch exceeds the 100-character limit"""
    payload = {"branch": "A" * 101}
    response = await client.patch("/students/me", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_my_profile_branch_blank_string_coerced_to_none(client, student_token):
    """Confirm that a blank branch is coerced to None"""
    response = await client.patch(
        "/students/me", json={"branch": ""}, headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 200
    assert response.json()["branch"] is None


@pytest.mark.asyncio
async def test_update_my_profile_year_min_boundary_succeeds(client, student_token):
    """Validate that profile update succeeds when year is exactly at the minimum value of 1"""
    payload = {"year": 1}
    response = await client.patch("/students/me", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    assert response.json()["year"] == 1


@pytest.mark.asyncio
async def test_update_my_profile_year_max_boundary_succeeds(client, student_token):
    """Validate that profile update succeeds when year is exactly at the maximum value of 5"""
    payload = {"year": 5}
    response = await client.patch("/students/me", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    assert response.json()["year"] == 5


@pytest.mark.asyncio
async def test_update_my_profile_year_below_min_fails(client, student_token):
    """Validate that profile update is rejected when year is below the minimum value of 1"""
    payload = {"year": 0}
    response = await client.patch("/students/me", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_my_profile_year_above_max_fails(client, student_token):
    """Validate that profile update is rejected when year exceeds the maximum value of 5"""
    payload = {"year": 6}
    response = await client.patch("/students/me", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_my_profile_year_invalid_type_fails(client, student_token):
    """Validate that profile update is rejected when year is not a valid integer"""
    payload = {"year": "not-a-year"}
    response = await client.patch("/students/me", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_my_profile_interests_max_items_boundary_succeeds(client, student_token):
    """Validate that profile update succeeds when interests has exactly 10 items"""
    interests = [f"Interest{i}" for i in range(10)]
    payload = {"interests": interests}
    response = await client.patch("/students/me", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    assert len(response.json()["interests"]) == 10


@pytest.mark.asyncio
async def test_update_my_profile_interests_over_max_items_fails(client, student_token):
    """Validate that profile update is rejected when interests has more than 10 items"""
    interests = [f"Interest{i}" for i in range(11)]
    payload = {"interests": interests}
    response = await client.patch("/students/me", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_my_profile_interest_item_max_length_boundary_succeeds(client, student_token):
    """Validate that profile update succeeds when an interest item is exactly at the 30-character limit"""
    payload = {"interests": ["A" * 30]}
    response = await client.patch("/students/me", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    assert response.json()["interests"] == ["A" * 30]


@pytest.mark.asyncio
async def test_update_my_profile_interest_item_over_max_length_fails(client, student_token):
    """Validate that profile update is rejected when an interest item exceeds the 30-character limit"""
    payload = {"interests": ["A" * 31]}
    response = await client.patch("/students/me", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_my_profile_interests_trims_whitespace_and_removes_duplicates(client, student_token):
    """Confirm that interest items are trimmed of whitespace and de-duplicated after trimming"""
    payload = {"interests": [" AI ", "AI", " ML", "ML "]}
    response = await client.patch("/students/me", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    assert response.json()["interests"] == ["AI", "ML"]


@pytest.mark.asyncio
async def test_update_my_profile_interests_drops_blank_items(client, student_token):
    """Confirm that blank/whitespace-only interest items are dropped rather than stored"""
    payload = {"interests": ["Music", "   ", "Art"]}
    response = await client.patch("/students/me", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    assert response.json()["interests"] == ["Music", "Art"]


@pytest.mark.asyncio
async def test_update_my_profile_interests_null_defaults_to_empty_list(client, student_token):
    """Confirm that explicitly sending interests as null resets it to an empty list"""
    await client.patch(
        "/students/me", json={"interests": ["Chess"]}, headers={"Authorization": f"Bearer {student_token}"}
    )

    response = await client.patch(
        "/students/me", json={"interests": None}, headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 200
    assert response.json()["interests"] == []


@pytest.mark.asyncio
async def test_update_my_profile_without_token_fails(client):
    """Verify that profile update is rejected when no authentication token is provided"""
    response = await client.patch("/students/me", json={"bio": "Should not apply"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.asyncio
async def test_update_my_profile_with_admin_token_fails(client, admin_token):
    """Verify that profile update is rejected for a user with the campus admin role"""
    response = await client.patch(
        "/students/me", json={"bio": "Admin attempt"}, headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 401
    body = response.json()
    assert body["message"] == "Invalid token"


# ==== {student_id} (public profile) ====

@pytest.mark.asyncio
async def test_view_public_profile_success_for_student(client, student_token, seed_college):
    """Verify that a student can view another student's public profile within the same college"""
    other_payload = {
        "email": "public.target@knit.edu.in",
        "full_name": "Public Target",
        "password": "Target@123",
        "confirm_password": "Target@123",
        "role": "STUDENT"
    }
    other_signup = await client.post("/auth/signup", json=other_payload)
    other_token = other_signup.json()["access_token"]

    other_profile = await client.get("/students/me", headers={"Authorization": f"Bearer {other_token}"})
    other_student_id = other_profile.json()["student_id"]

    response = await client.get(
        f"/students/{other_student_id}", headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["student_id"] == other_student_id
    assert body["full_name"] == "Public Target"
    assert "email" not in body
    assert "bio" not in body
    assert "interests" not in body
    assert "roll_no" not in body


@pytest.mark.asyncio
async def test_view_public_profile_success_for_admin(client, admin_token):
    """Verify that a campus admin can view a student's public profile within their own college"""
    college_payload = {
        "name": "Admin Profile View College",
        "email_suffix": "newcollege.edu",
        "description": "Onboarding the admin's own college so it has a college_id for profile visibility"
    }
    await client.post(
        "/college/onboarding", json=college_payload, headers={"Authorization": f"Bearer {admin_token}"}
    )

    student_payload = {
        "email": "target@newcollege.edu",
        "full_name": "Admin View Target",
        "password": "Target@123",
        "confirm_password": "Target@123",
        "role": "STUDENT"
    }
    student_signup = await client.post("/auth/signup", json=student_payload)
    student_token = student_signup.json()["access_token"]

    my_profile = await client.get("/students/me", headers={"Authorization": f"Bearer {student_token}"})
    student_id = my_profile.json()["student_id"]

    response = await client.get(f"/students/{student_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    assert response.json()["student_id"] == student_id


@pytest.mark.asyncio
async def test_view_public_profile_admin_without_college_returns_404(client, admin_token, student_token):
    """Confirm that an admin who has not onboarded a college cannot view any student's public profile"""
    my_profile = await client.get("/students/me", headers={"Authorization": f"Bearer {student_token}"})
    student_id = my_profile.json()["student_id"]

    response = await client.get(f"/students/{student_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Student profile not found"


@pytest.mark.asyncio
async def test_view_public_profile_nonexistent_returns_404(client, student_token):
    """Verify that viewing a nonexistent student id returns not found"""
    response = await client.get("/students/999999", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Student profile not found"


@pytest.mark.asyncio
async def test_view_public_profile_cross_college_returns_404(client, student_token):
    """Verify that viewing a student's profile from a different college returns not found"""
    admin_payload = {
        "email": "admin@otherstudent.edu.in",
        "full_name": "Other Student Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "CAMPUS_ADMIN"
    }
    admin_signup = await client.post("/auth/signup", json=admin_payload)
    other_admin_token = admin_signup.json()["access_token"]

    college_payload = {
        "name": "Other Student College",
        "email_suffix": "otherstudent.edu.in",
        "description": "A separate college for cross-college profile visibility tests"
    }
    await client.post(
        "/college/onboarding", json=college_payload, headers={"Authorization": f"Bearer {other_admin_token}"}
    )

    other_student_payload = {
        "email": "target@otherstudent.edu.in",
        "full_name": "Other College Target",
        "password": "Target@123",
        "confirm_password": "Target@123",
        "role": "STUDENT"
    }
    other_student_signup = await client.post("/auth/signup", json=other_student_payload)
    other_student_token = other_student_signup.json()["access_token"]

    other_profile = await client.get("/students/me", headers={"Authorization": f"Bearer {other_student_token}"})
    other_student_id = other_profile.json()["student_id"]

    response = await client.get(
        f"/students/{other_student_id}", headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Student profile not found"


@pytest.mark.asyncio
async def test_view_public_profile_invalid_id_type_fails(client, student_token):
    """Validate that requesting a non-integer student_id path parameter is rejected"""
    response = await client.get("/students/not-an-id", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_view_public_profile_without_token_fails(client, student_token):
    """Verify that viewing a public profile is rejected when no authentication token is provided"""
    my_profile = await client.get("/students/me", headers={"Authorization": f"Bearer {student_token}"})
    student_id = my_profile.json()["student_id"]

    response = await client.get(f"/students/{student_id}")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.asyncio
async def test_view_public_profile_joined_clubs_only_includes_approved_active_memberships(client, student_token):
    """Verify that a public profile's joined_clubs only lists APPROVED memberships in ACTIVE clubs"""
    club_payload = {
        "name": "Public View Club",
        "description": "A club created to verify public profile joined_clubs filtering",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    await client.post("/clubs", json=club_payload, headers={"Authorization": f"Bearer {student_token}"})

    my_profile = await client.get("/students/me", headers={"Authorization": f"Bearer {student_token}"})
    student_id = my_profile.json()["student_id"]

    response = await client.get(f"/students/{student_id}", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    club_names = [c["name"] for c in response.json()["joined_clubs"]]
    assert "Public View Club" in club_names


@pytest.mark.asyncio
async def test_update_my_profile_year_float_value_fails(client, student_token):
    """Validate that profile update is rejected when year is a non-integer float"""
    payload = {"year": 2.5}
    response = await client.patch("/students/me", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_my_profile_explicit_null_clears_previously_set_fields(client, student_token):
    """Confirm that explicitly sending null for bio, roll_no, branch, and year clears each field"""
    initial_payload = {"bio": "Set bio", "roll_no": "CS001", "branch": "CSE", "year": 3}
    await client.patch("/students/me", json=initial_payload, headers={"Authorization": f"Bearer {student_token}"})

    clear_payload = {"bio": None, "roll_no": None, "branch": None, "year": None}
    response = await client.patch(
        "/students/me", json=clear_payload, headers={"Authorization": f"Bearer {student_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["bio"] is None
    assert body["roll_no"] is None
    assert body["branch"] is None
    assert body["year"] is None


@pytest.mark.asyncio
async def test_view_own_profile_via_public_endpoint_hides_private_fields(client, student_token):
    """Verify that viewing your own profile through the public endpoint returns only public fields"""
    await client.patch(
        "/students/me",
        json={"bio": "Private bio", "roll_no": "CS999", "interests": ["Chess"]},
        headers={"Authorization": f"Bearer {student_token}"}
    )
    my_profile = await client.get("/students/me", headers={"Authorization": f"Bearer {student_token}"})
    student_id = my_profile.json()["student_id"]

    response = await client.get(f"/students/{student_id}", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["student_id"] == student_id
    assert "email" not in body
    assert "bio" not in body
    assert "interests" not in body
    assert "roll_no" not in body


@pytest.mark.asyncio
async def test_update_my_profile_interests_dedup_is_case_sensitive(client, student_token):
    """Confirm that interest dedup is exact-match only, so differently-cased duplicates are both kept"""
    payload = {"interests": ["AI", "ai", "Ai"]}
    response = await client.patch("/students/me", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    assert response.json()["interests"] == ["AI", "ai", "Ai"]


@pytest.mark.asyncio
async def test_update_my_profile_interests_non_string_items_fail(client, student_token):
    """Validate that profile update is rejected when interests contains non-string items"""
    payload = {"interests": [1, 2, 3]}
    response = await client.patch("/students/me", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_my_profile_joined_clubs_membership_role_reflects_leader(client, student_token):
    """Verify that joined_clubs reports LEADER as the membership_role for a club the student created"""
    payload = {
        "name": "Role Check Club",
        "description": "A club used to verify membership_role reporting for its leader",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    await client.post("/clubs", json=payload, headers={"Authorization": f"Bearer {student_token}"})

    response = await client.get("/students/me", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    club = next(c for c in response.json()["joined_clubs"] if c["name"] == "Role Check Club")
    assert club["membership_role"] == "LEADER"


@pytest.mark.asyncio
async def test_update_my_profile_bio_unicode_and_emoji_is_preserved(client, student_token):
    """Confirm that unicode and emoji characters in bio are stored and returned without corruption"""
    payload = {"bio": "café enthusiast ☕🎉 日本語"}
    response = await client.patch("/students/me", json=payload, headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    assert response.json()["bio"] == "café enthusiast ☕🎉 日本語"


@pytest.mark.asyncio
async def test_view_public_profile_negative_id_returns_404_not_422(client, student_token):
    """Verify that a negative student_id is treated as a valid but nonexistent id, returning 404"""
    response = await client.get("/students/-1", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Student profile not found"


@pytest.mark.asyncio
async def test_view_public_profile_zero_id_returns_404_not_422(client, student_token):
    """Verify that a student_id of zero is treated as a valid but nonexistent id, returning 404"""
    response = await client.get("/students/0", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Student profile not found"
