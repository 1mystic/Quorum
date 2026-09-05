import asyncio
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, Request
from app.exceptions import AppException
from fastapi.responses import JSONResponse
from app.api import (
    auth_router, tenant_router, tenant_info_router, member_router, group_router,
    public_group_router, event_router, announcement_router, request_router,
    notification_router, certificate_router, public_certificate_router, ai_router,
    ledger_router, insights_router, methods_router, participation_router, decision_router
)
from app.core.tenancy import verify_tenant_scope
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

@asynccontextmanager
async def lifespan(_: FastAPI):
    """Warm the LLM connection before the first member question arrives."""
    from app.agent import providers

    task = asyncio.create_task(providers.warm_up())
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(title="Quorum",
    description="Backend API for Quorum, a multi-tenant community operations platform.",
    lifespan=lifespan,
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", include_in_schema=False)
async def health():
    """No DB round trip on purpose: a host's uptime probe should reflect
    whether the process itself is alive, not whether the database is
    reachable this instant - a slow DB should not flap the whole service."""
    return {"status": "ok"}

@app.exception_handler(AppException)
async def handle_app_exc(request: Request, exc: AppException):
    content = {"message": exc.message}
    content.update(getattr(exc, "extra", {}))
    return JSONResponse(
        status_code=exc.status_code,
        content=content,
    )

# Global, no tenant context yet: account creation and onboarding a new tenant.
app.include_router(auth_router, prefix="/api")
app.include_router(tenant_router, prefix="/api")

# Global, deliberately public and cross-tenant: marketing landing page and
# certificate verification. See the routers themselves for why.
app.include_router(public_group_router, prefix="/api")
app.include_router(public_certificate_router, prefix="/api")

# Global, deliberately public and unauthenticated: a Method Card is a
# property of the mathematics, not of a tenant (docs/STATS_API.md section 4).
app.include_router(methods_router, prefix="/api")

# Every other route is tenant-scoped. verify_tenant_scope is the one place
# that checks the {slug} in the URL against the tenant_id/tenant_slug claims
# in the caller's JWT - see app/core/tenancy.py. Never trust the URL alone.
tenant_api = APIRouter(prefix="/api/t/{slug}", dependencies=[Depends(verify_tenant_scope)])
tenant_api.include_router(tenant_info_router)
tenant_api.include_router(member_router)
tenant_api.include_router(group_router)
tenant_api.include_router(event_router)
tenant_api.include_router(announcement_router)
tenant_api.include_router(request_router)
tenant_api.include_router(notification_router)
tenant_api.include_router(certificate_router)
tenant_api.include_router(ai_router)
tenant_api.include_router(ledger_router)
tenant_api.include_router(insights_router)
tenant_api.include_router(participation_router)
tenant_api.include_router(decision_router)
app.include_router(tenant_api)
