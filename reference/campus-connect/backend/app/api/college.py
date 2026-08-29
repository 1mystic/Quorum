from fastapi import APIRouter, Depends, Security
from app.schemas import CollegeOnboardingRequest, CollegeOnboardingResponse
from app.services import CollegeService
from app.core.di import get_college_service, get_user_info

college_router = APIRouter(prefix="/college", tags=["College Onboarding"])

@college_router.post("/onboarding", response_model=CollegeOnboardingResponse)
async def onboarding(
    data: CollegeOnboardingRequest,
    payload: dict = Security(get_user_info, scopes=["CAMPUS_ADMIN"]),
    service: CollegeService = Depends(get_college_service) 
):
    
    return await service.onboarding(payload,data)

