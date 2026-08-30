"""
Card C.10. `docs/STATS_API.md` section 4's read surface.

`insights_router` mounts under `/api/t/{slug}` like every other tenant-scoped
router. `methods_router` is deliberately separate and mounted at the top
level, unauthenticated: a Method Card is a property of the mathematics, not
of a tenant, and the trust story only works if a sceptical reader can check
it without an account (section 4's `GET /api/methods/{method_id}`).
"""
from fastapi import APIRouter, Depends, Query, Security

from app.schemas import PacksResponse, InsightEnvelopeResponse, InsightHealthResponse
from app.services import InsightsService
from app.core.di import get_insights_service, get_user_info
from app.core.tenancy import get_current_tenant_id
from app.exceptions import InsightNotFoundError
from app.stats import registry

insights_router = APIRouter(prefix="/insights", tags=["Insights"])
methods_router = APIRouter(prefix="/methods", tags=["Methods"])


@insights_router.get("/packs", response_model=PacksResponse)
async def list_packs(
    tenant_id: int = Depends(get_current_tenant_id),
    _: dict = Security(get_user_info, scopes=["MEMBER", "TENANT_ADMIN"]),
    service: InsightsService = Depends(get_insights_service),
):
    return await service.packs(tenant_id)


@insights_router.get("/health", response_model=InsightHealthResponse)
async def insights_health(
    tenant_id: int = Depends(get_current_tenant_id),
    _: dict = Security(get_user_info, scopes=["MEMBER", "TENANT_ADMIN"]),
    service: InsightsService = Depends(get_insights_service),
):
    return await service.health(tenant_id)


@insights_router.get("/{pack_id}", response_model=list[InsightEnvelopeResponse])
async def pack_insights(
    pack_id: str,
    tenant_id: int = Depends(get_current_tenant_id),
    _: dict = Security(get_user_info, scopes=["MEMBER", "TENANT_ADMIN"]),
    service: InsightsService = Depends(get_insights_service),
):
    return await service.pack_insights(tenant_id, pack_id)


@insights_router.get("/{pack_id}/{service_id}", response_model=InsightEnvelopeResponse)
async def one_insight(
    pack_id: str,
    service_id: str,
    scope: str = Query(""),
    tenant_id: int = Depends(get_current_tenant_id),
    _: dict = Security(get_user_info, scopes=["MEMBER", "TENANT_ADMIN"]),
    service: InsightsService = Depends(get_insights_service),
):
    return await service.one_insight(tenant_id, pack_id, service_id, scope)


@insights_router.get("/{pack_id}/{service_id}/history", response_model=list[InsightEnvelopeResponse])
async def insight_history(
    pack_id: str,
    service_id: str,
    scope: str = Query(""),
    tenant_id: int = Depends(get_current_tenant_id),
    _: dict = Security(get_user_info, scopes=["MEMBER", "TENANT_ADMIN"]),
    service: InsightsService = Depends(get_insights_service),
):
    return await service.history(tenant_id, service_id, scope)


@methods_router.get("/{method_id}")
async def get_method_card(method_id: str):
    try:
        return registry.method_card(method_id).to_wire()
    except KeyError:
        raise InsightNotFoundError()
