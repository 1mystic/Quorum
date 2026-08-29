from fastapi import APIRouter, Depends, Security
from app.schemas import TenantOnboardingRequest, TenantOnboardingResponse
from app.services import TenantService
from app.core.di import get_tenant_service, get_user_info

tenant_router = APIRouter(prefix="/tenant", tags=["Tenant Onboarding"])

@tenant_router.post("/onboarding", response_model=TenantOnboardingResponse)
async def onboarding(
    data: TenantOnboardingRequest,
    payload: dict = Security(get_user_info, scopes=["TENANT_ADMIN"]),
    service: TenantService = Depends(get_tenant_service) 
):
    
    return await service.onboarding(payload,data)

