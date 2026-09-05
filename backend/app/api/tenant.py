from fastapi import APIRouter, Depends, Security
from app.schemas import TenantOnboardingRequest, TenantOnboardingResponse, TenantInfoResponse
from app.services import TenantService
from app.core.di import get_tenant_service, get_user_info
from app.core.tenancy import get_current_tenant_id

tenant_router = APIRouter(prefix="/tenant", tags=["Tenant Onboarding"])

@tenant_router.post("/onboarding", response_model=TenantOnboardingResponse)
async def onboarding(
    data: TenantOnboardingRequest,
    payload: dict = Security(get_user_info, scopes=["TENANT_ADMIN"]),
    service: TenantService = Depends(get_tenant_service)
):

    return await service.onboarding(payload,data)


# Mounted under /api/t/{slug} (see main.py's tenant_api block), not here:
# every authenticated tenant member/admin needs this to render the app shell
# (name, vertical, enabled packs) - it is a read, not an oversight action.
tenant_info_router = APIRouter(prefix="/tenant", tags=["Tenant"])

@tenant_info_router.get("", response_model=TenantInfoResponse)
async def get_tenant_info(
    tenant_id: int = Depends(get_current_tenant_id),
    _: dict = Security(get_user_info, scopes=["MEMBER", "TENANT_ADMIN"]),
    service: TenantService = Depends(get_tenant_service),
):
    return await service.get_info(tenant_id)

