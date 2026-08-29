
import pytest


# ==== me (get own profile) ====

@pytest.mark.asyncio
async def test_get_my_profile_success(client, member_token):
    """Verify that a member can fetch their own profile with all expected fields"""
    response = await client.get("/members/me", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Group Member"
    assert body["email"] == "group.member@knit.edu.in"
    assert body["bio"] is None
    assert body["interests"] == []
    assert body["roll_no"] is None
    assert body["branch"] is None
    assert body["year"] is None
    assert body["joined_groups"] == []
    assert "member_id" in body
    assert "created_at" in body


@pytest.mark.asyncio
async def test_get_my_profile_without_token_fails(client):
    """Verify that fetching own profile is rejected when no authentication token is provided"""
    response = await client.get("/members/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.asyncio
async def test_get_my_profile_with_admin_token_fails(client, admin_token):
    """Verify that fetching own profile is rejected for a user with the campus admin role"""
    response = await client.get("/members/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 401
    body = response.json()
    assert body["message"] == "Invalid token"


@pytest.mark.asyncio
async def test_get_my_profile_joined_groups_only_includes_approved_active_memberships(client, member_token):
    """Verify that joined_groups only lists groups where membership is APPROVED and the group is ACTIVE"""
    payload = {
        "name": "Own Group Membership",
        "description": "A group the member leads and is auto-approved into",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})

    response = await client.get("/members/me", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    body = response.json()
    group_names = [c["name"] for c in body["joined_groups"]]
    assert "Own Group Membership" in group_names


@pytest.mark.asyncio
async def test_get_my_profile_joined_groups_excludes_pending_official_group(client, member_token):
    """Confirm that a PENDING (not yet approved) official group is not listed in joined_groups"""
    payload = {
        "name": "Pending Membership Group",
        "description": "An official group that stays pending admin approval",
        "category": "Technical",
        "type": "OFFICIAL"
    }
    await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})

    response = await client.get("/members/me", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    group_names = [c["name"] for c in response.json()["joined_groups"]]
    assert "Pending Membership Group" not in group_names


# ==== me (update own profile) ====

@pytest.mark.asyncio
async def test_update_my_profile_success_all_fields(client, member_token):
    """Verify that updating all profile fields at once succeeds and returns the confirmation message"""
    payload = {
        "bio": "I love robotics and chess",
        "interests": ["Robotics", "Chess"],
        "roll_no": "CS2024001",
        "branch": "Computer Science",
        "year": 2
    }
    response = await client.patch("/members/me", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["bio"] == "I love robotics and chess"
    assert body["interests"] == ["Robotics", "Chess"]
    assert body["roll_no"] == "CS2024001"
    assert body["branch"] == "Computer Science"
    assert body["year"] == 2
    assert body["message"] == "Profile updated successfully"


@pytest.mark.asyncio
async def test_update_my_profile_partial_update_leaves_other_fields_unchanged(client, member_token):
    """Verify that updating only one field leaves previously set fields untouched"""
    first_payload = {"bio": "Initial bio", "branch": "Electronics", "year": 1}
    await client.patch("/members/me", json=first_payload, headers={"Authorization": f"Bearer {member_token}"})

    second_payload = {"bio": "Updated bio only"}
    response = await client.patch(
        "/members/me", json=second_payload, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["bio"] == "Updated bio only"
    assert body["branch"] == "Electronics"
    assert body["year"] == 1


@pytest.mark.asyncio
async def test_update_my_profile_empty_payload_is_a_noop(client, member_token):
    """Confirm that updating with an empty payload leaves all fields unchanged"""
    payload = {"bio": "Untouched bio", "branch": "Mechanical", "year": 3}
    await client.patch("/members/me", json=payload, headers={"Authorization": f"Bearer {member_token}"})

    response = await client.patch("/members/me", json={}, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["bio"] == "Untouched bio"
    assert body["branch"] == "Mechanical"
    assert body["year"] == 3


@pytest.mark.asyncio
async def test_update_my_profile_bio_max_length_boundary_succeeds(client, member_token):
    """Validate that profile update succeeds when bio is exactly at the 500-character limit"""
    payload = {"bio": "A" * 500}
    response = await client.patch("/members/me", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    assert response.json()["bio"] == "A" * 500


@pytest.mark.asyncio
async def test_update_my_profile_bio_over_max_length_fails(client, member_token):
    """Validate that profile update is rejected when bio exceeds the 500-character limit"""
    payload = {"bio": "A" * 501}
    response = await client.patch("/members/me", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_my_profile_bio_blank_string_coerced_to_none(client, member_token):
    """Confirm that a whitespace-only bio is coerced to None instead of being stored literally"""
    await client.patch("/members/me", json={"bio": "Some bio"}, headers={"Authorization": f"Bearer {member_token}"})

    response = await client.patch(
        "/members/me", json={"bio": "   "}, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 200
    assert response.json()["bio"] is None


@pytest.mark.asyncio
async def test_update_my_profile_roll_no_max_length_boundary_succeeds(client, member_token):
    """Validate that profile update succeeds when roll_no is exactly at the 50-character limit"""
    payload = {"roll_no": "A" * 50}
    response = await client.patch("/members/me", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    assert response.json()["roll_no"] == "A" * 50


@pytest.mark.asyncio
async def test_update_my_profile_roll_no_over_max_length_fails(client, member_token):
    """Validate that profile update is rejected when roll_no exceeds the 50-character limit"""
    payload = {"roll_no": "A" * 51}
    response = await client.patch("/members/me", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_my_profile_roll_no_blank_string_coerced_to_none(client, member_token):
    """Confirm that a blank roll_no is coerced to None"""
    response = await client.patch(
        "/members/me", json={"roll_no": "  "}, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 200
    assert response.json()["roll_no"] is None


@pytest.mark.asyncio
async def test_update_my_profile_branch_max_length_boundary_succeeds(client, member_token):
    """Validate that profile update succeeds when branch is exactly at the 100-character limit"""
    payload = {"branch": "A" * 100}
    response = await client.patch("/members/me", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    assert response.json()["branch"] == "A" * 100


@pytest.mark.asyncio
async def test_update_my_profile_branch_over_max_length_fails(client, member_token):
    """Validate that profile update is rejected when branch exceeds the 100-character limit"""
    payload = {"branch": "A" * 101}
    response = await client.patch("/members/me", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_my_profile_branch_blank_string_coerced_to_none(client, member_token):
    """Confirm that a blank branch is coerced to None"""
    response = await client.patch(
        "/members/me", json={"branch": ""}, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 200
    assert response.json()["branch"] is None


@pytest.mark.asyncio
async def test_update_my_profile_year_min_boundary_succeeds(client, member_token):
    """Validate that profile update succeeds when year is exactly at the minimum value of 1"""
    payload = {"year": 1}
    response = await client.patch("/members/me", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    assert response.json()["year"] == 1


@pytest.mark.asyncio
async def test_update_my_profile_year_max_boundary_succeeds(client, member_token):
    """Validate that profile update succeeds when year is exactly at the maximum value of 5"""
    payload = {"year": 5}
    response = await client.patch("/members/me", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    assert response.json()["year"] == 5


@pytest.mark.asyncio
async def test_update_my_profile_year_below_min_fails(client, member_token):
    """Validate that profile update is rejected when year is below the minimum value of 1"""
    payload = {"year": 0}
    response = await client.patch("/members/me", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_my_profile_year_above_max_fails(client, member_token):
    """Validate that profile update is rejected when year exceeds the maximum value of 5"""
    payload = {"year": 6}
    response = await client.patch("/members/me", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_my_profile_year_invalid_type_fails(client, member_token):
    """Validate that profile update is rejected when year is not a valid integer"""
    payload = {"year": "not-a-year"}
    response = await client.patch("/members/me", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_my_profile_interests_max_items_boundary_succeeds(client, member_token):
    """Validate that profile update succeeds when interests has exactly 10 items"""
    interests = [f"Interest{i}" for i in range(10)]
    payload = {"interests": interests}
    response = await client.patch("/members/me", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    assert len(response.json()["interests"]) == 10


@pytest.mark.asyncio
async def test_update_my_profile_interests_over_max_items_fails(client, member_token):
    """Validate that profile update is rejected when interests has more than 10 items"""
    interests = [f"Interest{i}" for i in range(11)]
    payload = {"interests": interests}
    response = await client.patch("/members/me", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_my_profile_interest_item_max_length_boundary_succeeds(client, member_token):
    """Validate that profile update succeeds when an interest item is exactly at the 30-character limit"""
    payload = {"interests": ["A" * 30]}
    response = await client.patch("/members/me", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    assert response.json()["interests"] == ["A" * 30]


@pytest.mark.asyncio
async def test_update_my_profile_interest_item_over_max_length_fails(client, member_token):
    """Validate that profile update is rejected when an interest item exceeds the 30-character limit"""
    payload = {"interests": ["A" * 31]}
    response = await client.patch("/members/me", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_my_profile_interests_trims_whitespace_and_removes_duplicates(client, member_token):
    """Confirm that interest items are trimmed of whitespace and de-duplicated after trimming"""
    payload = {"interests": [" AI ", "AI", " ML", "ML "]}
    response = await client.patch("/members/me", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    assert response.json()["interests"] == ["AI", "ML"]


@pytest.mark.asyncio
async def test_update_my_profile_interests_drops_blank_items(client, member_token):
    """Confirm that blank/whitespace-only interest items are dropped rather than stored"""
    payload = {"interests": ["Music", "   ", "Art"]}
    response = await client.patch("/members/me", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    assert response.json()["interests"] == ["Music", "Art"]


@pytest.mark.asyncio
async def test_update_my_profile_interests_null_defaults_to_empty_list(client, member_token):
    """Confirm that explicitly sending interests as null resets it to an empty list"""
    await client.patch(
        "/members/me", json={"interests": ["Chess"]}, headers={"Authorization": f"Bearer {member_token}"}
    )

    response = await client.patch(
        "/members/me", json={"interests": None}, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 200
    assert response.json()["interests"] == []


@pytest.mark.asyncio
async def test_update_my_profile_without_token_fails(client):
    """Verify that profile update is rejected when no authentication token is provided"""
    response = await client.patch("/members/me", json={"bio": "Should not apply"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.asyncio
async def test_update_my_profile_with_admin_token_fails(client, admin_token):
    """Verify that profile update is rejected for a user with the campus admin role"""
    response = await client.patch(
        "/members/me", json={"bio": "Admin attempt"}, headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 401
    body = response.json()
    assert body["message"] == "Invalid token"


# ==== {member_id} (public profile) ====

@pytest.mark.asyncio
async def test_view_public_profile_success_for_member(client, member_token, seed_tenant):
    """Verify that a member can view another member's public profile within the same tenant"""
    other_payload = {
        "email": "public.target@knit.edu.in",
        "full_name": "Public Target",
        "password": "Target@123",
        "confirm_password": "Target@123",
        "role": "MEMBER"
    }
    other_signup = await client.post("/auth/signup", json=other_payload)
    other_token = other_signup.json()["access_token"]

    other_profile = await client.get("/members/me", headers={"Authorization": f"Bearer {other_token}"})
    other_member_id = other_profile.json()["member_id"]

    response = await client.get(
        f"/members/{other_member_id}", headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["member_id"] == other_member_id
    assert body["full_name"] == "Public Target"
    assert "email" not in body
    assert "bio" not in body
    assert "interests" not in body
    assert "roll_no" not in body


@pytest.mark.asyncio
async def test_view_public_profile_success_for_admin(client, admin_token):
    """Verify that a campus admin can view a member's public profile within their own tenant"""
    tenant_payload = {
        "name": "Admin Profile View Tenant",
        "email_suffix": "newtenant.edu",
        "description": "Onboarding the admin's own tenant so it has a tenant_id for profile visibility"
    }
    await client.post(
        "/tenant/onboarding", json=tenant_payload, headers={"Authorization": f"Bearer {admin_token}"}
    )

    member_payload = {
        "email": "target@newtenant.edu",
        "full_name": "Admin View Target",
        "password": "Target@123",
        "confirm_password": "Target@123",
        "role": "MEMBER"
    }
    member_signup = await client.post("/auth/signup", json=member_payload)
    member_token = member_signup.json()["access_token"]

    my_profile = await client.get("/members/me", headers={"Authorization": f"Bearer {member_token}"})
    member_id = my_profile.json()["member_id"]

    response = await client.get(f"/members/{member_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 200
    assert response.json()["member_id"] == member_id


@pytest.mark.asyncio
async def test_view_public_profile_admin_without_tenant_returns_404(client, admin_token, member_token):
    """Confirm that an admin who has not onboarded a tenant cannot view any member's public profile"""
    my_profile = await client.get("/members/me", headers={"Authorization": f"Bearer {member_token}"})
    member_id = my_profile.json()["member_id"]

    response = await client.get(f"/members/{member_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Member profile not found"


@pytest.mark.asyncio
async def test_view_public_profile_nonexistent_returns_404(client, member_token):
    """Verify that viewing a nonexistent member id returns not found"""
    response = await client.get("/members/999999", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Member profile not found"


@pytest.mark.asyncio
async def test_view_public_profile_cross_tenant_returns_404(client, member_token):
    """Verify that viewing a member's profile from a different tenant returns not found"""
    admin_payload = {
        "email": "admin@othermember.edu.in",
        "full_name": "Other Member Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "TENANT_ADMIN"
    }
    admin_signup = await client.post("/auth/signup", json=admin_payload)
    other_admin_token = admin_signup.json()["access_token"]

    tenant_payload = {
        "name": "Other Member Tenant",
        "email_suffix": "othermember.edu.in",
        "description": "A separate tenant for cross-tenant profile visibility tests"
    }
    await client.post(
        "/tenant/onboarding", json=tenant_payload, headers={"Authorization": f"Bearer {other_admin_token}"}
    )

    other_member_payload = {
        "email": "target@othermember.edu.in",
        "full_name": "Other Tenant Target",
        "password": "Target@123",
        "confirm_password": "Target@123",
        "role": "MEMBER"
    }
    other_member_signup = await client.post("/auth/signup", json=other_member_payload)
    other_member_token = other_member_signup.json()["access_token"]

    other_profile = await client.get("/members/me", headers={"Authorization": f"Bearer {other_member_token}"})
    other_member_id = other_profile.json()["member_id"]

    response = await client.get(
        f"/members/{other_member_id}", headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Member profile not found"


@pytest.mark.asyncio
async def test_view_public_profile_invalid_id_type_fails(client, member_token):
    """Validate that requesting a non-integer member_id path parameter is rejected"""
    response = await client.get("/members/not-an-id", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_view_public_profile_without_token_fails(client, member_token):
    """Verify that viewing a public profile is rejected when no authentication token is provided"""
    my_profile = await client.get("/members/me", headers={"Authorization": f"Bearer {member_token}"})
    member_id = my_profile.json()["member_id"]

    response = await client.get(f"/members/{member_id}")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.asyncio
async def test_view_public_profile_joined_groups_only_includes_approved_active_memberships(client, member_token):
    """Verify that a public profile's joined_groups only lists APPROVED memberships in ACTIVE groups"""
    group_payload = {
        "name": "Public View Group",
        "description": "A group created to verify public profile joined_groups filtering",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    await client.post("/groups", json=group_payload, headers={"Authorization": f"Bearer {member_token}"})

    my_profile = await client.get("/members/me", headers={"Authorization": f"Bearer {member_token}"})
    member_id = my_profile.json()["member_id"]

    response = await client.get(f"/members/{member_id}", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    group_names = [c["name"] for c in response.json()["joined_groups"]]
    assert "Public View Group" in group_names


@pytest.mark.asyncio
async def test_update_my_profile_year_float_value_fails(client, member_token):
    """Validate that profile update is rejected when year is a non-integer float"""
    payload = {"year": 2.5}
    response = await client.patch("/members/me", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_update_my_profile_explicit_null_clears_previously_set_fields(client, member_token):
    """Confirm that explicitly sending null for bio, roll_no, branch, and year clears each field"""
    initial_payload = {"bio": "Set bio", "roll_no": "CS001", "branch": "CSE", "year": 3}
    await client.patch("/members/me", json=initial_payload, headers={"Authorization": f"Bearer {member_token}"})

    clear_payload = {"bio": None, "roll_no": None, "branch": None, "year": None}
    response = await client.patch(
        "/members/me", json=clear_payload, headers={"Authorization": f"Bearer {member_token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["bio"] is None
    assert body["roll_no"] is None
    assert body["branch"] is None
    assert body["year"] is None


@pytest.mark.asyncio
async def test_view_own_profile_via_public_endpoint_hides_private_fields(client, member_token):
    """Verify that viewing your own profile through the public endpoint returns only public fields"""
    await client.patch(
        "/members/me",
        json={"bio": "Private bio", "roll_no": "CS999", "interests": ["Chess"]},
        headers={"Authorization": f"Bearer {member_token}"}
    )
    my_profile = await client.get("/members/me", headers={"Authorization": f"Bearer {member_token}"})
    member_id = my_profile.json()["member_id"]

    response = await client.get(f"/members/{member_id}", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["member_id"] == member_id
    assert "email" not in body
    assert "bio" not in body
    assert "interests" not in body
    assert "roll_no" not in body


@pytest.mark.asyncio
async def test_update_my_profile_interests_dedup_is_case_sensitive(client, member_token):
    """Confirm that interest dedup is exact-match only, so differently-cased duplicates are both kept"""
    payload = {"interests": ["AI", "ai", "Ai"]}
    response = await client.patch("/members/me", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    assert response.json()["interests"] == ["AI", "ai", "Ai"]


@pytest.mark.asyncio
async def test_update_my_profile_interests_non_string_items_fail(client, member_token):
    """Validate that profile update is rejected when interests contains non-string items"""
    payload = {"interests": [1, 2, 3]}
    response = await client.patch("/members/me", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_get_my_profile_joined_groups_membership_role_reflects_leader(client, member_token):
    """Verify that joined_groups reports LEADER as the membership_role for a group the member created"""
    payload = {
        "name": "Role Check Group",
        "description": "A group used to verify membership_role reporting for its leader",
        "category": "Technical",
        "type": "UNOFFICIAL"
    }
    await client.post("/groups", json=payload, headers={"Authorization": f"Bearer {member_token}"})

    response = await client.get("/members/me", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    group = next(c for c in response.json()["joined_groups"] if c["name"] == "Role Check Group")
    assert group["membership_role"] == "LEADER"


@pytest.mark.asyncio
async def test_update_my_profile_bio_unicode_and_emoji_is_preserved(client, member_token):
    """Confirm that unicode and emoji characters in bio are stored and returned without corruption"""
    payload = {"bio": "café enthusiast ☕🎉 日本語"}
    response = await client.patch("/members/me", json=payload, headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 200
    assert response.json()["bio"] == "café enthusiast ☕🎉 日本語"


@pytest.mark.asyncio
async def test_view_public_profile_negative_id_returns_404_not_422(client, member_token):
    """Verify that a negative member_id is treated as a valid but nonexistent id, returning 404"""
    response = await client.get("/members/-1", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Member profile not found"


@pytest.mark.asyncio
async def test_view_public_profile_zero_id_returns_404_not_422(client, member_token):
    """Verify that a member_id of zero is treated as a valid but nonexistent id, returning 404"""
    response = await client.get("/members/0", headers={"Authorization": f"Bearer {member_token}"})
    assert response.status_code == 404
    body = response.json()
    assert body["message"] == "Member profile not found"
