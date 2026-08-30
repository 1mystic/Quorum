"""
Card C.10. Requires a real Postgres TEST_DATABASE_URL (same constraint as
`test_tenancy.py`).

Three things this file proves against a live database:

1. The read surface serves the calm, honest "not enough data" shape for a
   service that has never run, at 200, never 404/422 (docs/STATS_API.md
   section 5).
2. A pack the tenant has not enabled 409s with a `reason`, per the same
   section.
3. `InsightMaterializer.materialize_all`, run against real seeded `Request`
   rows through the real `RequestRepository`/adapter, produces a genuine
   `insight_runs` row with a real number, end to end - model to adapter to
   pure function to cache to API. This is the DB-backed twin of
   `tests/unit/services/test_insight_materializer.py`; it monkeypatches the
   same not-yet-implemented `streams.reduce.request_spells` for the same
   reason that file documents at its top, and needs nothing else changed once
   the real reducer lands.
"""
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import tenant_path


@pytest.fixture
async def rwa_tenant(db_session):
    from app.models import Tenant

    tenant = Tenant(
        name="Vaikunth Heights", slug="vaikunth-insights", vertical="rwa_society",
        enabled_packs=["reliability_ops"],
    )
    db_session.add(tenant)
    await db_session.flush()
    await db_session.refresh(tenant)
    return tenant


async def _signup_member(client, tenant_slug: str, email: str) -> str:
    payload = {
        "email": email, "full_name": "Insights Test Member", "password": "Member@123",
        "confirm_password": "Member@123", "role": "MEMBER", "tenant_slug": tenant_slug,
    }
    response = await client.post("/api/auth/signup", json=payload)
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_a_service_that_has_never_run_is_a_calm_200(client, rwa_tenant):
    slug = rwa_tenant.slug
    token = await _signup_member(client, slug, "member@vaikunth-insights.example")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(
        tenant_path(slug, "/insights/reliability_ops/survival.median_resolution_days"),
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["evidence"]["insufficient_data"] is True
    assert body["evidence"]["n"] == 0


@pytest.mark.asyncio
async def test_a_disabled_pack_409s_with_a_reason(client, rwa_tenant):
    slug = rwa_tenant.slug
    token = await _signup_member(client, slug, "member2@vaikunth-insights.example")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get(
        tenant_path(slug, "/insights/governance_insight/voting.condorcet_winner"),
        headers=headers,
    )
    assert response.status_code == 409
    assert response.json()["reason"] == "pack_disabled"


@pytest.mark.asyncio
async def test_the_materializer_produces_a_real_cached_run(client, db_session, rwa_tenant, monkeypatch):
    """
    Seeds real `Request` rows for the tenant, runs `InsightMaterializer`
    against the real repository/adapter path, and asserts the API serves back
    a genuine number from the cache - never computing it itself.
    """
    from app.stats.streams import reduce as stream_reduce
    from app.stats.streams.request import RequestEvent, RequestSpell
    from app.services.insight_materializer import InsightMaterializer, default_window

    def toy_request_spells(events, window, *, reopen_policy="new_spell"):
        by_ref = defaultdict(list)
        for event in events:
            by_ref[event.request_ref].append(event)
        spells = []
        for ref, group in by_ref.items():
            group.sort(key=lambda e: e.at)
            opened = group[0]
            terminal = next((e for e in group if e.kind == "resolved"), None)
            if terminal is not None:
                duration_hours = (terminal.at - opened.at).total_seconds() / 3600.0
                spells.append(RequestSpell(
                    request_ref=ref, opened_at=opened.at, at_risk_from=opened.at,
                    left_truncated=False, duration_hours=duration_hours,
                    duration_active_hours=None, event_observed=True, outcome="resolved",
                    terminal_at=terminal.at, censoring="none", interval_lo_hours=None,
                    interval_hi_hours=None, first_response_hours=None, paused_hours=0.0,
                    reopened_count=0, duplicate_count=0, category=opened.category or "other",
                ))
            else:
                duration_hours = (window.end - opened.at).total_seconds() / 3600.0
                spells.append(RequestSpell(
                    request_ref=ref, opened_at=opened.at, at_risk_from=opened.at,
                    left_truncated=False, duration_hours=duration_hours,
                    duration_active_hours=None, event_observed=False, outcome=None,
                    terminal_at=None, censoring="administrative", interval_lo_hours=None,
                    interval_hi_hours=None, first_response_hours=None, paused_hours=0.0,
                    reopened_count=0, duplicate_count=0, category=opened.category or "other",
                ))
        return tuple(spells)

    monkeypatch.setattr(stream_reduce, "request_spells", toy_request_spells)

    slug = rwa_tenant.slug
    token = await _signup_member(client, slug, "member3@vaikunth-insights.example")
    headers = {"Authorization": f"Bearer {token}"}

    group_response = await client.post(
        tenant_path(slug, "/groups"), headers=headers,
        json={"name": "Maintenance Committee", "description": "Runs the pipes",
              "category": "Technical", "type": "UNOFFICIAL"},
    )
    assert group_response.status_code == 200, group_response.text
    group_id = group_response.json()["id"]

    now = datetime.now(timezone.utc)
    for i in range(35):
        create = await client.post(
            tenant_path(slug, "/requests"), headers=headers,
            json={
                "group_id": group_id, "category": "water_supply",
                "title": f"No water tower {i}", "description": "Third day running, please fix.",
            },
        )
        assert create.status_code == 200, create.text
        request_id = create.json()["id"]
        resolve = await client.patch(
            tenant_path(slug, f"/requests/{request_id}/resolve"), headers=headers,
        )
        assert resolve.status_code == 200, resolve.text
    for i in range(5):
        create = await client.post(
            tenant_path(slug, "/requests"), headers=headers,
            json={
                "group_id": group_id, "category": "water_supply",
                "title": f"Still open {i}", "description": "Not fixed yet.",
            },
        )
        assert create.status_code == 200, create.text

    materializer = InsightMaterializer(db_session, rwa_tenant)
    window = default_window(now=now, tenant_timezone=rwa_tenant.timezone)
    runs = await materializer.materialize_all(window)
    await db_session.commit()

    survival_run = next(r for r in runs if r.service == "survival.median_resolution_days")
    assert survival_run.insufficient is False
    assert survival_run.n == 40
    assert survival_run.n_censored == 5
    assert survival_run.payload["value"] is not None

    response = await client.get(
        tenant_path(slug, "/insights/reliability_ops/survival.median_resolution_days"),
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()["evidence"]
    assert body["insufficient_data"] is False
    assert body["n"] == 40
    assert body["value"] == survival_run.payload["value"]
