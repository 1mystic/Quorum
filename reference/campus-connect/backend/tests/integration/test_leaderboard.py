import json
import pytest
from datetime import datetime, timedelta, timezone

from app.models import Club, Event


def future_time(hours: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def month_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


# ==== fixtures ====

@pytest.fixture
async def leader(client, seed_college):
    """Student fixture owning an active club"""
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
    club = await client.post("/clubs", headers=headers, data={"data": json.dumps(payload)})
    return headers, club.json()["id"]


@pytest.fixture
async def member(client, seed_college, leader):
    """Approved club member fixture"""
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
    approve_payload = {"action": "APPROVED"}
    await client.patch(
        f"/clubs/{club_id}/requests/{join.json()['id']}",
        headers=leader_headers,
        json=approve_payload,
    )
    return headers


@pytest.fixture
async def started_event(client, db_session, leader, member):
    """Backdated published event fixture"""
    leader_headers, club_id = leader
    payload = {
        "club_id": club_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(2),
        "ends_at": future_time(4),
    }
    create = await client.post("/events", headers=leader_headers, data={"data": json.dumps(payload)})
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/publish", headers=leader_headers)
    registration = await client.post(f"/events/{event_id}/register", headers=member)
    registration_id = registration.json()["registration_id"]

    event = await db_session.get(Event, event_id)
    event.starts_at = datetime.now(timezone.utc) - timedelta(hours=1)
    event.ends_at = datetime.now(timezone.utc) + timedelta(hours=1)
    await db_session.flush()   # <- flush, not commit — stays inside the same transaction

    return leader_headers, event_id, registration_id


# ==== 1. happy path ====

@pytest.mark.asyncio
async def test_leaderboard_scores_events_members_and_issues_this_month(client, db_session, leader, member, started_event):
    """Verify that club score reflects monthly events, members, and issues"""
    leader_headers, club_id = leader
    _, event_id, registration_id = started_event

    attendance_payload = {"checked_in": True}
    await client.patch(
        f"/events/{event_id}/registrations/{registration_id}/attendance",
        headers=leader_headers, json=attendance_payload,
    )

    issue_payload = {
        "club_id": club_id,
        "category": "CLUB",
        "title": "Cannot access club resources",
        "description": "I am unable to view the shared drive for this club",
    }
    issue = await client.post("/issues", headers=member, json=issue_payload)
    await client.patch(f"/issues/{issue.json()['id']}/resolve", headers=leader_headers)

    response = await client.get("/leaderboard", headers=leader_headers)
    assert response.status_code == 200
    entry = next(e for e in response.json() if e["club_id"] == club_id)

    assert entry["events_held"] == 1
    assert entry["new_members"] == 2
    assert entry["issues_resolved"] == 1
    assert entry["attendance_rate"] == 1.0
    assert entry["attendance_bonus"] == 200
    assert entry["score"] == 40 * 1 + 5 * 2 + 10 * 1 + 200


# ==== 2. validation ====
# GET /leaderboard takes no request body or query parameters, so there is no
# input-shape validation surface beyond authentication (see section 6).


# ==== 3. business rules ====

@pytest.mark.asyncio
async def test_leaderboard_excludes_non_active_clubs(client, db_session, leader, started_event):
    """Verify that non-active clubs are excluded from leaderboard"""
    leader_headers, club_id = leader

    club = await db_session.get(Club, club_id)
    club.status = "PENDING"
    await db_session.flush()

    response = await client.get("/leaderboard", headers=leader_headers)
    assert response.status_code == 200
    assert club_id not in {e["club_id"] for e in response.json()}


@pytest.mark.asyncio
async def test_leaderboard_excludes_activity_before_this_month(client, db_session, leader, started_event):
    """Verify that past month activity is excluded from score"""
    leader_headers, club_id = leader
    _, event_id, _ = started_event

    event = await db_session.get(Event, event_id)
    event.starts_at = month_start() - timedelta(days=1)
    event.ends_at = event.starts_at + timedelta(hours=2)
    await db_session.flush()

    response = await client.get("/leaderboard", headers=leader_headers)
    entry = next(e for e in response.json() if e["club_id"] == club_id)
    assert entry["events_held"] == 0
    assert entry["attendance_bonus"] == 0
    assert entry["score"] == 5 * entry["new_members"]


@pytest.mark.asyncio
async def test_leaderboard_only_counts_resolved_issues(client, leader, member):
    """Verify that only resolved issues contribute to score"""
    leader_headers, club_id = leader
    issue_payload = {
        "club_id": club_id,
        "category": "CLUB",
        "title": "Still open issue",
        "description": "This issue is deliberately left unresolved for the test",
    }
    await client.post("/issues", headers=member, json=issue_payload)

    response = await client.get("/leaderboard", headers=leader_headers)
    entry = next(e for e in response.json() if e["club_id"] == club_id)
    assert entry["issues_resolved"] == 0
    assert entry["score"] == 5 * entry["new_members"]


# ==== 4. boundary ====

@pytest.mark.asyncio
async def test_leaderboard_includes_event_exactly_at_month_start(client, db_session, leader, started_event):
    """Verify that events starting at month's boundary are counted"""
    leader_headers, club_id = leader
    _, event_id, _ = started_event

    event = await db_session.get(Event, event_id)
    event.starts_at = month_start()
    event.ends_at = month_start() + timedelta(hours=1)
    await db_session.flush()

    response = await client.get("/leaderboard", headers=leader_headers)
    entry = next(e for e in response.json() if e["club_id"] == club_id)
    assert entry["events_held"] == 1
    assert entry["attendance_rate"] == 0.0


@pytest.mark.asyncio
async def test_leaderboard_empty_when_college_has_no_active_clubs(client, student_token):
    """Verify that empty leaderboard is returned when no active clubs exist"""
    response = await client.get("/leaderboard", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    assert response.json() == []

# ==== 5. edge cases ====

@pytest.mark.asyncio
async def test_leaderboard_ranks_are_sequential_and_ordered_by_score_desc(client, student_token, started_event):
    """Verify that ranks are sequential and sorted by score descending"""
    # Create a second club (Astronomy Club) with a new student token under the same college
    payload_b = {
        "email": "leader_b@knit.edu.in",
        "full_name": "Leader B",
        "password": "Test@1234",
        "confirm_password": "Test@1234",
        "role": "STUDENT",
    }
    signup_b = await client.post("/auth/signup", json=payload_b)
    headers_b = {"Authorization": f"Bearer {signup_b.json()['access_token']}"}

    club_payload_b = {
        "name": "Astronomy Club",
        "description": "Stargazing and space enthusiasts",
        "category": "Science",
        "type": "UNOFFICIAL",
    }
    await client.post("/clubs", headers=headers_b, data={"data": json.dumps(club_payload_b)})

    response = await client.get("/leaderboard", headers={"Authorization": f"Bearer {student_token}"})
    assert response.status_code == 200
    body = response.json()
    
    assert len(body) >= 2

    # Verify ranks are sequential (1, 2, ...)
    ranks = [e["rank"] for e in body]
    assert ranks == list(range(1, len(body) + 1))

    # Verify scores are sorted in descending order
    scores = [e["score"] for e in body]
    assert scores == sorted(scores, reverse=True)

    # Verify Club A (Robotics Club, high score) is ranked above Club B (Astronomy Club, low score)
    robotics = next(e for e in body if e["name"] == "Robotics Club")
    astronomy = next(e for e in body if e["name"] == "Astronomy Club")
    assert robotics["rank"] < astronomy["rank"]
    assert robotics["score"] > astronomy["score"]



# @pytest.mark.asyncio
# async def test_leaderboard_event_with_no_registrations_counts_as_zero_attendance(client, db_session, leader, member):
#     """Verify that events with zero registrations count as 0% attendance"""
#     leader_headers, club_id = leader

#     # event 1: one registration, fully checked in -> 100% attendance
#     attended_payload = {
#         "club_id": club_id,
#         "title": "Attended Workshop",
#         "description": "An event with one checked-in registrant",
#         "venue": "Lab 204, Main Block",
#         "starts_at": future_time(2),
#         "ends_at": future_time(4),
#     }
#     attended = await client.post("/events", headers=leader_headers, data={"data": json.dumps(attended_payload)})
#     attended_id = attended.json()["id"]
#     await client.patch(f"/events/{attended_id}/publish", headers=leader_headers)
#     registration = await client.post(f"/events/{attended_id}/register", headers=member)
#     registration_id = registration.json()["registration_id"]

#     # event 2: published, zero registrations
#     empty_payload = {
#         "club_id": club_id,
#         "title": "Empty Room Workshop",
#         "description": "A published event that nobody registered for",
#         "venue": "Lab 204, Main Block",
#         "starts_at": future_time(2),
#         "ends_at": future_time(4),
#     }
#     empty = await client.post("/events", headers=leader_headers, data={"data": json.dumps(empty_payload)})
#     empty_id = empty.json()["id"]
#     await client.patch(f"/events/{empty_id}/publish", headers=leader_headers)

#     for event_id in (attended_id, empty_id):
#         event = await db_session.get(Event, event_id)
#         event.starts_at = datetime.now(timezone.utc) - timedelta(hours=1)
#         event.ends_at = datetime.now(timezone.utc) + timedelta(hours=1)
#     await db_session.flush()

#     attendance_payload = {"checked_in": True}
#     await client.patch(
#         f"/events/{attended_id}/registrations/{registration_id}/attendance",
#         headers=leader_headers, json=attendance_payload,
#     )

#     response = await client.get("/leaderboard", headers=leader_headers)
#     entry = next(e for e in response.json() if e["club_id"] == club_id)

#     assert entry["events_held"] == 2
#     # Expected attendance rate is the average across all published events: (1.0 + 0.0) / 2 = 0.5
#     assert entry["attendance_rate"] == 0.5
#     assert entry["attendance_bonus"] == 100

# ==== 6. auth / authorization ====

@pytest.mark.asyncio
async def test_leaderboard_without_token_fails(client):
    """Verify that requesting leaderboard without token is rejected"""
    response = await client.get("/leaderboard")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.asyncio
async def test_leaderboard_scoped_to_own_college(client, leader):
    """Verify that leaderboard is scoped to user's college"""
    leader_headers, club_id = leader

    admin_payload = {
        "email": "admin@lbother.edu.in",
        "full_name": "Other College Admin",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "CAMPUS_ADMIN",
    }
    admin_signup = await client.post("/auth/signup", json=admin_payload)
    other_admin_token = admin_signup.json()["access_token"]

    college_payload = {
        "name": "Other Leaderboard College",
        "email_suffix": "lbother.edu.in",
        "description": "A separate college used for leaderboard tenant isolation",
    }
    await client.post(
        "/college/onboarding", json=college_payload, headers={"Authorization": f"Bearer {other_admin_token}"}
    )

    other_student_payload = {
        "email": "leader@lbother.edu.in",
        "full_name": "Foreign Leader",
        "password": "Leader@123",
        "confirm_password": "Leader@123",
        "role": "STUDENT",
    }
    other_signup = await client.post("/auth/signup", json=other_student_payload)
    other_headers = {"Authorization": f"Bearer {other_signup.json()['access_token']}"}

    foreign_club_payload = {
        "name": "Foreign College Club",
        "description": "A club that belongs to a different college",
        "category": "Technical",
        "type": "UNOFFICIAL",
    }
    foreign_club = await client.post("/clubs", headers=other_headers, data={"data": json.dumps(foreign_club_payload)})
    foreign_club_id = foreign_club.json()["id"]

    response = await client.get("/leaderboard", headers=leader_headers)
    assert response.status_code == 200
    club_ids = {e["club_id"] for e in response.json()}
    assert club_id in club_ids
    assert foreign_club_id not in club_ids