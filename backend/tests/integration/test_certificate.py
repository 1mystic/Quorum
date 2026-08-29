import pytest
from datetime import datetime, timedelta, timezone

from app.models import Certificate, Event, RegistrationResult


def future_time(hours: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


@pytest.fixture(autouse=True)
def mock_storage_url(monkeypatch):
    """No S3 access available: stub storage.get_url() so certificate download tests don't need real AWS."""
    from app.core.storage import storage
    monkeypatch.setattr(storage, "get_url", lambda key, signed=False, expires_in=3600: f"https://fake-s3.test/{key}")


# ==== fixtures ====

@pytest.fixture
async def leader(client, seed_tenant):
    """A member who owns an active group. Yields (headers, group_id)."""
    payload = {
        "email": "cert-leader@knit.edu.in",
        "full_name": "Cert Group Leader",
        "password": "Test@1234",
        "confirm_password": "Test@1234",
        "role": "MEMBER",
    }
    signup = await client.post("/auth/signup", json=payload)
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    payload = {
        "name": "Cert Robotics Group",
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
        "email": "cert-member@knit.edu.in",
        "full_name": "Cert Group Member",
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
async def second_member(client, leader):
    """Another approved member of the leader's group, distinct from `member`."""
    leader_headers, group_id = leader
    payload = {
        "email": "cert-second@knit.edu.in",
        "full_name": "Cert Second Member",
        "password": "Test@1234",
        "confirm_password": "Test@1234",
        "role": "MEMBER",
    }
    signup = await client.post("/auth/signup", json=payload)
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    join = await client.post(f"/groups/{group_id}/join", headers=headers)
    approve_payload = {"action": "APPROVED"}
    await client.patch(
        f"/groups/{group_id}/requests/{join.json()['id']}",
        headers=leader_headers,
        json=approve_payload,
    )
    return headers


@pytest.fixture
async def outsider(client, seed_tenant):
    """A member of the same tenant who belongs to no group."""
    payload = {
        "email": "cert-outsider@knit.edu.in",
        "full_name": "Cert Outsider Member",
        "password": "Test@1234",
        "confirm_password": "Test@1234",
        "role": "MEMBER",
    }
    signup = await client.post("/auth/signup", json=payload)
    return {"Authorization": f"Bearer {signup.json()['access_token']}"}


@pytest.fixture
async def two_checked_in(client, db_session, leader, member, second_member):
    """Two members registered and checked in, event already started."""
    leader_headers, group_id = leader
    payload = {
        "group_id": group_id,
        "title": "Line Follower Workshop",
        "description": "Hands-on session on building a line follower bot",
        "venue": "Lab 204, Main Block",
        "starts_at": future_time(2),
        "ends_at": future_time(4),
    }
    create = await client.post("/events", headers=leader_headers, json=payload)
    event_id = create.json()["id"]
    await client.patch(f"/events/{event_id}/publish", headers=leader_headers)

    first = await client.post(f"/events/{event_id}/register", headers=member)
    first_registration_id = first.json()["registration_id"]
    second = await client.post(f"/events/{event_id}/register", headers=second_member)
    second_registration_id = second.json()["registration_id"]

    event = await db_session.get(Event, event_id)
    event.starts_at = datetime.now(timezone.utc) - timedelta(hours=1)
    event.ends_at = datetime.now(timezone.utc) + timedelta(hours=1)
    await db_session.flush()

    payload = {"checked_in": True}
    await client.patch(
        f"/events/{event_id}/registrations/{first_registration_id}/attendance",
        headers=leader_headers,
        json=payload,
    )
    await client.patch(
        f"/events/{event_id}/registrations/{second_registration_id}/attendance",
        headers=leader_headers,
        json=payload,
    )

    return leader_headers, event_id, first_registration_id, second_registration_id


@pytest.fixture
async def certificate_for_member(db_session, two_checked_in):
    """Directly creates a Certificate row for the winner registration from two_checked_in."""
    _, event_id, member_registration_id, _ = two_checked_in

    certificate = Certificate(
        registration_id=member_registration_id,
        serial="CC-LFW-2026-00001",
        result=RegistrationResult.WINNER,
        issued_at=datetime.now(timezone.utc),
    )
    db_session.add(certificate)
    await db_session.flush()

    return event_id, member_registration_id, certificate


# ==== my certificates ====

@pytest.mark.asyncio
async def test_my_certificates_returns_earned_certificate(client, certificate_for_member, member):
    """Verify that a member with an earned certificate receives it in their list"""
    response = await client.get("/certificates/me", headers=member)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["serial"] == "CC-LFW-2026-00001"
    assert body[0]["result"] == "WINNER"
    assert "download_url" in body[0]


@pytest.mark.asyncio
async def test_my_certificates_empty_for_member_with_none(client, outsider):
    """Confirm that a member with zero certificates receives an empty list"""
    response = await client.get("/certificates/me", headers=outsider)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_my_certificates_without_token_fails(client):
    """Ensure that listing certificates is rejected without an access token"""
    response = await client.get("/certificates/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.asyncio
async def test_my_certificates_by_non_member_fails(client, admin_token):
    """Ensure that a non-member cannot access the member certificate list"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.get("/certificates/me", headers=headers)
    assert response.status_code == 401


# ==== verify certificate ====

@pytest.mark.asyncio
async def test_verify_certificate_valid_serial_no_auth_needed(client, certificate_for_member):
    """Verify that a valid serial is confirmed as authentic without any auth headers"""
    response = await client.get("/certificates/verify/CC-LFW-2026-00001")
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["serial"] == "CC-LFW-2026-00001"
    assert body["result"] == "WINNER"


@pytest.mark.asyncio
async def test_verify_certificate_unknown_serial_fails(client):
    """Confirm that verifying a non-existent serial returns not found"""
    response = await client.get("/certificates/verify/CC-FAKE-9999-00000")
    assert response.status_code == 404
    assert response.json()["message"] == "Certificate not found"


# ==== download certificate ====

@pytest.mark.asyncio
async def test_download_certificate_success(client, certificate_for_member, member):
    """Verify that the owning member receives a signed download URL"""
    _, _, certificate = certificate_for_member
    response = await client.get(f"/certificates/{certificate.serial}/download", headers=member)
    assert response.status_code == 200
    body = response.json()
    assert body["serial"] == certificate.serial
    assert body["filename"] == f"{certificate.serial}.pdf"
    assert body["expires_in"] == 3600
    assert "download_url" in body


@pytest.mark.asyncio
async def test_download_certificate_by_non_owner_fails(client, certificate_for_member, outsider):
    """Ensure that a member who does not own the certificate cannot download it"""
    _, _, certificate = certificate_for_member
    response = await client.get(f"/certificates/{certificate.serial}/download", headers=outsider)
    assert response.status_code == 404
    assert response.json()["message"] == "Certificate not found"


@pytest.mark.asyncio
async def test_download_certificate_unknown_serial_fails(client, member):
    """Confirm that downloading a non-existent serial returns not found"""
    response = await client.get("/certificates/FAKE-SERIAL/download", headers=member)
    assert response.status_code == 404
    assert response.json()["message"] == "Certificate not found"


@pytest.mark.asyncio
async def test_download_certificate_without_token_fails(client, certificate_for_member):
    """Ensure that downloading is rejected without an access token"""
    _, _, certificate = certificate_for_member
    response = await client.get(f"/certificates/{certificate.serial}/download")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


# ==== multiple certificates ====

@pytest.mark.asyncio
async def test_my_certificates_lists_multiple_earned_certificates(client, db_session, two_checked_in, member):
    """Verify that a member with certificates from multiple events receives all of them"""
    _, event_id, member_registration_id, second_registration_id = two_checked_in

    first_certificate = Certificate(
        registration_id=member_registration_id,
        serial="CC-LFW-2026-00001",
        result=RegistrationResult.WINNER,
        issued_at=datetime.now(timezone.utc),
    )
    db_session.add(first_certificate)

    second_certificate = Certificate(
        registration_id=second_registration_id,
        serial="CC-LFW-2026-00002",
        result=RegistrationResult.RUNNER_UP,
        issued_at=datetime.now(timezone.utc),
    )
    db_session.add(second_certificate)
    await db_session.flush()

    response = await client.get("/certificates/me", headers=member)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["serial"] == "CC-LFW-2026-00001"


@pytest.mark.asyncio
async def test_my_certificates_lists_multiple_events_same_member(client, db_session, leader, member):
    """Verify that a member's certificates from two different events both appear in their list"""
    leader_headers, group_id = leader

    events = []
    for i in range(2):
        payload = {
            "group_id": group_id,
            "title": f"Workshop {i}",
            "description": f"Test workshop number {i} for multi-certificate testing",
            "venue": "Lab 204",
            "starts_at": future_time(2 + i * 10),
            "ends_at": future_time(4 + i * 10),
        }
        create = await client.post("/events", headers=leader_headers, json=payload)
        event_id = create.json()["id"]
        await client.patch(f"/events/{event_id}/publish", headers=leader_headers)
        registration = await client.post(f"/events/{event_id}/register", headers=member)
        events.append((event_id, registration.json()["registration_id"]))

    for i, (event_id, registration_id) in enumerate(events):
        certificate = Certificate(
            registration_id=registration_id,
            serial=f"CC-MULTI-2026-0000{i+1}",
            result=RegistrationResult.PARTICIPANT,
            issued_at=datetime.now(timezone.utc),
        )
        db_session.add(certificate)
    await db_session.flush()

    response = await client.get("/certificates/me", headers=member)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    serials = {item["serial"] for item in body}
    assert serials == {"CC-MULTI-2026-00001", "CC-MULTI-2026-00002"}


# ==== result variations ====

@pytest.mark.asyncio
async def test_verify_certificate_runner_up_result(client, db_session, two_checked_in):
    """Verify that a RUNNER_UP-result certificate verifies correctly, not just WINNER"""
    _, event_id, _, second_registration_id = two_checked_in
    certificate = Certificate(
        registration_id=second_registration_id,
        serial="CC-LFW-2026-00050",
        result=RegistrationResult.RUNNER_UP,
        issued_at=datetime.now(timezone.utc),
    )
    db_session.add(certificate)
    await db_session.flush()

    response = await client.get("/certificates/verify/CC-LFW-2026-00050")
    assert response.status_code == 200
    assert response.json()["result"] == "RUNNER_UP"


@pytest.mark.asyncio
async def test_verify_certificate_participant_result(client, db_session, two_checked_in):
    """Verify that a PARTICIPANT-result certificate verifies correctly, not just WINNER"""
    _, event_id, _, second_registration_id = two_checked_in
    certificate = Certificate(
        registration_id=second_registration_id,
        serial="CC-LFW-2026-00099",
        result=RegistrationResult.PARTICIPANT,
        issued_at=datetime.now(timezone.utc),
    )
    db_session.add(certificate)
    await db_session.flush()

    response = await client.get("/certificates/verify/CC-LFW-2026-00099")
    assert response.status_code == 200
    assert response.json()["result"] == "PARTICIPANT"


@pytest.mark.asyncio
async def test_download_certificate_runner_up_result(client, db_session, two_checked_in, second_member):
    """Verify that a RUNNER_UP certificate can be downloaded by its owning member"""
    _, event_id, _, second_registration_id = two_checked_in
    certificate = Certificate(
        registration_id=second_registration_id,
        serial="CC-LFW-2026-00051",
        result=RegistrationResult.RUNNER_UP,
        issued_at=datetime.now(timezone.utc),
    )
    db_session.add(certificate)
    await db_session.flush()

    response = await client.get(f"/certificates/{certificate.serial}/download", headers=second_member)
    assert response.status_code == 200
    body = response.json()
    assert body["serial"] == "CC-LFW-2026-00051"