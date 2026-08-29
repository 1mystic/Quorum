"""
Shared pytest fixtures.

Includes an autouse fixture that pins the AI module's LLM client to
deterministic mock mode for the entire suite, regardless of whether
ANTHROPIC_API_KEY happens to be set in backend/.env. Tests must stay
offline, deterministic and free - they exercise the mock fallback
contract, not the real Anthropic API. The real key is still used by the
running dev server; only tests are pinned to the mock.
"""
import json
from pathlib import Path
from typing import AsyncGenerator

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy import event, text

from app.core.database import Base, get_db
from app.core.config import settings
from app.core import rls
from app.models.tenant import Tenant
from app.agent import llm_client
from main import app


MAILHOG_API_BASE = "http://localhost:8025/api"


@pytest_asyncio.fixture()
async def clear_mailhog():
    try:
        httpx.delete(f"{MAILHOG_API_BASE}/v1/messages")
    except Exception:
        pass
    yield


TEST_DATABASE_URL = settings.TEST_DATABASE_URL
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(autouse=True)
def force_llm_mock_mode(monkeypatch):
    monkeypatch.setattr(llm_client, "_API_KEY", "")
    # Clear the response cache so a value cached by a real call in a prior
    # run cannot leak into a mock-mode assertion.
    llm_client._cache.clear()
    yield
    llm_client._cache.clear()


@pytest_asyncio.fixture(scope="session")
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Tests build the schema straight from the ORM metadata rather than
        # `alembic upgrade head`, so the RLS migration's DDL never runs
        # against the test database unless it is applied here too. Kept in
        # sync with the migration via app.core.rls, the shared source.
        for statement in rls.enable_statements():
            await conn.execute(text(statement))
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


# Simple fixture — fast, used by most tests (no internal commits happen)
@pytest_asyncio.fixture()
async def db_session(setup_db) -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


# SAVEPOINT-based fixture — only for tests that hit an endpoint calling db.commit() internally
@pytest_asyncio.fixture()
# async def db_session_committing(setup_db) -> AsyncGenerator[AsyncSession, None]:
async def db_session(setup_db) -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.connect() as connection:
        outer_transaction = await connection.begin()
        session = TestSessionLocal(bind=connection)
        nested = await connection.begin_nested()

        @event.listens_for(session.sync_session, "after_transaction_end")
        def restart_savepoint(sess, transaction):
            nonlocal nested
            if not nested.is_active:
                nested = connection.sync_connection.begin_nested()

        try:
            yield session
        finally:
            await session.close()
            await outer_transaction.rollback()
            await connection.close()


class InterceptAsyncClient(AsyncClient):
    async def request(self, method: str, url, *args, **kwargs):
        method_upper = method.upper()
        url_str = str(url)
        from urllib.parse import urlparse
        path = urlparse(url_str).path
        
        parts = path.strip("/").split("/")
        # Tenant-scoped routes are /api/t/{slug}/..., so strip that prefix
        # before checking the domain-relative shape below.
        if len(parts) >= 3 and parts[0] == "api" and parts[1] == "t":
            parts = parts[3:]

        is_multipart_endpoint = False
        if method_upper == "POST":
            is_multipart_endpoint = len(parts) == 1 and parts[0] in ("groups", "events")
        elif method_upper == "PUT":
            if len(parts) == 2 and parts[0] in ("groups", "events"):
                try:
                    int(parts[1])
                    is_multipart_endpoint = True
                except ValueError:
                    pass
        elif method_upper == "PATCH":
            is_multipart_endpoint = len(parts) == 2 and parts[0] == "members" and parts[1] == "me"
        
        if is_multipart_endpoint and "json" in kwargs and kwargs["json"] is not None:
            payload = kwargs.pop("json")
            if "data" not in kwargs or kwargs["data"] is None:
                kwargs["data"] = {}
            kwargs["data"]["data"] = json.dumps(payload)
            
        return await super().request(method, url, *args, **kwargs)


@pytest_asyncio.fixture()
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with InterceptAsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture()
async def seed_tenant(db_session: AsyncSession) -> Tenant:
    # member signup needs a tenant to already exist, joined by slug rather
    # than by email domain (Campus Connect's email_suffix - see
    # docs/GLOSSARY.md for why that did not generalize past the campus
    # vertical).
    tenant = Tenant(
        name="Test University",
        slug="test-university",
        vertical="campus_club",
    )
    db_session.add(tenant)
    await db_session.flush()
    await db_session.refresh(tenant)
    return tenant


def tenant_path(slug: str, suffix: str) -> str:
    """/api/t/{slug}/... route builder, so tests read the slug once, not per call."""
    return f"/api/t/{slug}{suffix}"



_results_log = []
def pytest_runtest_makereport(item, call):
    if call.when == "call":
        outcome = "passed" if call.excinfo is None else "failed"
        _results_log.append({
            "test": item.nodeid,
            "outcome": outcome,
            "error": str(call.excinfo.value) if call.excinfo else None,
        })

def pytest_sessionfinish(session, exitstatus):
    Path("tests/reports").mkdir(parents=True, exist_ok=True)
    Path("tests/reports/results_log.json").write_text(json.dumps(_results_log, indent=2))

@pytest_asyncio.fixture()
async def admin_token(client):
    payload = {
        "email": "admin@newtenant.edu",
        "full_name": "Admin User",
        "password": "Admin@123",
        "confirm_password": "Admin@123",
        "role": "TENANT_ADMIN"
    }
    response = await client.post("/api/auth/signup", json=payload)
    body = response.json()
    return body["access_token"]


@pytest_asyncio.fixture()
async def member_token(client, seed_tenant):
    payload = {
        "email": "group.member@knit.edu.in",
        "full_name": "Group Member",
        "password": "Member@123",
        "confirm_password": "Member@123",
        "role": "MEMBER",
        "tenant_slug": seed_tenant.slug,
    }
    response = await client.post("/api/auth/signup", json=payload)
    body = response.json()
    return body["access_token"]
