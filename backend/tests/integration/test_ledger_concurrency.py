"""
Part 2 of the ledger concurrency card, proven the way the card demands: not a
single-threaded unit test that never exercises the race, but two independent
Postgres connections racing a real `LedgerService.verify_payment` call
against the same row.

The shared `client`/`db_session` fixtures the rest of the integration suite
uses are deliberately unsuitable here: they hand every request the same
`AsyncSession` object (rollback-based isolation, one shared transaction), and
a single `AsyncSession` is not safe for concurrent use, let alone able to
demonstrate a `SELECT ... FOR UPDATE` blocking a second real backend. This
file opens two genuinely separate sessions (`TestSessionLocal`, `NullPool`
means each gets its own real connection) against data committed for real, the
same shape production traffic has.
"""
import asyncio
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select, text

from tests.conftest import TestSessionLocal, test_engine
from app.core.database import Base
from app.core import rls
from app.core.tenancy import set_tenant_context
from app.models import (
    Tenant, User, UserRole, Member, Due, DueStatus, Payment, LedgerInstrument, LedgerStatus,
)
from app.repository import LedgerRepository, MemberRepository, UserRepository, TenantRepository
from app.services import LedgerService
from app.exceptions import PaymentAlreadySettledError


def _create_schema_and_rls(sync_conn) -> None:
    """
    The same job `conftest.setup_db` does, made idempotent (`checkfirst` on
    tables, `policy_already_applied` on RLS policies) so this module can
    build its own real, committing schema without fighting `setup_db`'s
    session-scoped fixture over event-loop lifetime - the two run against the
    same physical database either way, so idempotency is what actually
    matters here, not which fixture ran first.
    """
    Base.metadata.create_all(bind=sync_conn, checkfirst=True)
    for table in rls.TENANT_SCOPED_TABLES:
        if not rls.policy_already_applied(sync_conn, table):
            for statement in rls.enable_statements_for([table]):
                sync_conn.execute(text(statement))


@pytest_asyncio.fixture()
async def ensure_schema():
    async with test_engine.begin() as conn:
        await conn.run_sync(_create_schema_and_rls)
    yield


async def _seed_payment(amount_minor: int = 500_000) -> dict:
    """
    Commits a tenant, a member and a due+payment for real (not the shared
    rollback-based session), so two independent connections opened afterwards
    both see the same committed rows to race over.
    """
    unique = uuid.uuid4().hex[:8]
    async with TestSessionLocal() as session:
        tenant = Tenant(name=f"Race Society {unique}", slug=f"race-society-{unique}", vertical="rwa_society")
        session.add(tenant)
        await session.flush()
        await set_tenant_context(session, tenant.id)

        user = User(
            tenant_id=tenant.id, email=f"racer-{unique}@example.com", hashed_password="x",
            full_name="Race Member", role=UserRole.MEMBER,
        )
        session.add(user)
        await session.flush()

        member = Member(tenant_id=tenant.id, user_id=user.id)
        session.add(member)
        await session.flush()

        due = Due(
            tenant_id=tenant.id, member_id=member.id, category="maintenance_dues",
            amount_minor=amount_minor,
            issued_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
            due_at=datetime(2026, 7, 10, tzinfo=timezone.utc),
            status=DueStatus.OPEN,
        )
        session.add(due)
        await session.flush()

        payment = Payment(
            tenant_id=tenant.id, due_id=due.id, member_id=member.id, category="maintenance_dues",
            amount_minor=amount_minor, instrument=LedgerInstrument.UPI, status=LedgerStatus.PENDING,
            at=datetime(2026, 7, 3, 10, tzinfo=timezone.utc),
        )
        session.add(payment)
        await session.flush()

        ids = {
            "tenant_id": tenant.id, "user_id": user.id, "member_id": member.id,
            "due_id": due.id, "payment_id": payment.id,
        }
        await session.commit()
    return ids


async def _verify_via_a_fresh_connection(ids: dict):
    """
    Opens its own session (its own real Postgres backend, `NullPool`), builds
    the real `LedgerService` on it, and calls `verify_payment` exactly as the
    API route does. Returns ("ok", PaymentItem) or ("blocked", exception).
    """
    async with TestSessionLocal() as session:
        await set_tenant_context(session, ids["tenant_id"])
        ledger_repo = LedgerRepository(session, ids["tenant_id"])
        member_repo = MemberRepository(session)
        user_repo = UserRepository(session)
        tenant_repo = TenantRepository(session)
        service = LedgerService(ledger_repo, member_repo, user_repo, tenant_repo)
        payload = {"sub": str(ids["user_id"]), "role": "MEMBER"}
        try:
            item = await service.verify_payment(payload, ids["payment_id"])
            await session.commit()
            return "ok", item
        except Exception as exc:
            await session.rollback()
            return "blocked", exc


@pytest.mark.asyncio
async def test_concurrent_verify_payment_only_one_wins(ensure_schema):
    """
    The actual race: two coroutines, each on its own real connection, call
    `verify_payment` on the *same* payment at the same moment via
    `asyncio.gather`. `SELECT ... FOR UPDATE` in `get_payment_for_update`
    means the second call blocks on the first's row lock until the first
    transaction commits, then re-reads the now-SETTLED row and raises
    `PaymentAlreadySettledError` - it does not silently re-verify or
    double-credit the due.
    """
    ids = await _seed_payment(amount_minor=500_000)

    results = await asyncio.gather(
        _verify_via_a_fresh_connection(ids),
        _verify_via_a_fresh_connection(ids),
    )

    outcomes = [status for status, _ in results]
    assert outcomes.count("ok") == 1, f"expected exactly one winner, got {outcomes}"
    assert outcomes.count("blocked") == 1, f"expected exactly one loser, got {outcomes}"

    loser = next(exc for status, exc in results if status == "blocked")
    assert isinstance(loser, PaymentAlreadySettledError)

    # The due's paid amount must not be double-counted: exactly one
    # settlement of 500000 against a 500000 due, not two.
    async with TestSessionLocal() as session:
        await set_tenant_context(session, ids["tenant_id"])
        due = await session.get(Due, ids["due_id"])
        assert due.status == DueStatus.PAID

        result = await session.execute(
            select(Payment).where(Payment.due_id == ids["due_id"], Payment.status == LedgerStatus.SETTLED)
        )
        settled_payments = result.scalars().all()
        assert len(settled_payments) == 1
        assert sum(p.amount_minor for p in settled_payments) == 500_000


@pytest.mark.asyncio
async def test_concurrent_verify_payment_only_one_wins_across_many_trials(ensure_schema):
    """
    The single-trial version above could in principle pass by luck if
    asyncio's scheduler always happened to run one coroutine to completion
    before the other ever starts, which would prove nothing about the row
    lock. Repeating the race 15 times, each on a fresh payment, is the check
    that this is a real database-level exclusion and not a scheduling
    artifact: every single trial must land on exactly one winner.
    """
    trial_results = []
    for _ in range(15):
        ids = await _seed_payment(amount_minor=500_000)
        results = await asyncio.gather(
            _verify_via_a_fresh_connection(ids),
            _verify_via_a_fresh_connection(ids),
        )
        trial_results.append([status for status, _ in results])

    for outcomes in trial_results:
        assert outcomes.count("ok") == 1, f"a trial did not have exactly one winner: {outcomes}"
        assert outcomes.count("blocked") == 1, f"a trial did not have exactly one loser: {outcomes}"


@pytest.mark.asyncio
async def test_optimistic_lock_catches_a_lost_update_even_without_the_row_lock(ensure_schema):
    """
    `Due.version` is the second layer, for a code path that forgets the
    explicit row lock. Simulated directly: two sessions each load the same
    Due with a plain read (no `FOR UPDATE`), both mutate it, the first
    commits cleanly, and the second - still holding the pre-mutation version
    number - must fail loudly with `StaleDataError` rather than silently
    overwrite the first session's change.
    """
    from sqlalchemy.orm.exc import StaleDataError

    ids = await _seed_payment(amount_minor=500_000)

    async with TestSessionLocal() as session_a, TestSessionLocal() as session_b:
        await set_tenant_context(session_a, ids["tenant_id"])
        await set_tenant_context(session_b, ids["tenant_id"])

        due_a = await session_a.get(Due, ids["due_id"])
        due_b = await session_b.get(Due, ids["due_id"])
        assert due_a.version == due_b.version == 1

        due_a.status = DueStatus.PAID
        await session_a.commit()

        due_b.status = DueStatus.WAIVED
        with pytest.raises(StaleDataError):
            await session_b.commit()
        await session_b.rollback()

    async with TestSessionLocal() as session:
        await set_tenant_context(session, ids["tenant_id"])
        due = await session.get(Due, ids["due_id"])
        assert due.status == DueStatus.PAID, "the first session's committed write must survive"
        assert due.version == 2


@pytest.mark.asyncio
async def test_concurrent_verify_payment_on_different_payments_both_succeed(ensure_schema):
    """
    Negative control: the lock is per-row, not a blanket serialization of the
    whole ledger. Two different payments, verified concurrently, both
    succeed - proving the blocking above is really about the shared row, not
    an artifact of the test harness or a global lock.
    """
    ids_a = await _seed_payment(amount_minor=100_000)
    ids_b = await _seed_payment(amount_minor=200_000)

    results = await asyncio.gather(
        _verify_via_a_fresh_connection(ids_a),
        _verify_via_a_fresh_connection(ids_b),
    )

    assert [status for status, _ in results] == ["ok", "ok"]
