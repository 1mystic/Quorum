"""
Tenant-scoped routes live under /api/t/{slug}/... . This module is the one
place that checks the slug in the URL against the tenant_id/tenant_slug
claims signed into the caller's JWT, and it is a hard 403 on any mismatch.

Never trust the URL alone (docs/RULES.md section 5): a request for
/api/t/other-society/requests carrying a token issued for "my-society" must
fail here, before any repository runs a query.

This also sets the Postgres session variable app.tenant_id via set_config,
scoped to the current transaction (the third argument, is_local=true). Every
Postgres RLS policy added in the tenancy migration reads that same setting.
It is defense in depth: TenantScopedRepository should already be filtering by
tenant_id in every query, RLS is the backstop for the query that forgets to.
"""
from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.token import decode_token
from app.exceptions import AuthorizationError, TenantSlugMismatchError

_security = HTTPBearer()


async def verify_tenant_scope(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_security),
    db: AsyncSession = Depends(get_db),
) -> dict:
    payload = decode_token(credentials.credentials)

    slug = request.path_params.get("slug")
    if not slug:
        raise AuthorizationError()

    if payload.get("tenant_slug") != slug or payload.get("tenant_id") is None:
        raise TenantSlugMismatchError()

    await db.execute(
        text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
        {"tenant_id": str(payload["tenant_id"])},
    )
    request.state.tenant_id = payload["tenant_id"]

    return payload


def get_current_tenant_id(request: Request) -> int:
    """
    For DI functions in app.core.di that build a TenantScopedRepository. Only
    valid on routes mounted under /api/t/{slug}/..., where verify_tenant_scope
    has already run as a router-level dependency and set request.state.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    if tenant_id is None:
        raise AuthorizationError()
    return tenant_id
