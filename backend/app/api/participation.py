from fastapi import APIRouter, Depends, Security

from app.schemas import RecordParticipationEventRequest, ParticipationEventItem
from app.services import ParticipationService
from app.core.di import get_participation_service, get_user_info

participation_router = APIRouter(prefix="/participation", tags=["Participation"])


@participation_router.post("/events", response_model=ParticipationEventItem)
async def record_event(
    data: RecordParticipationEventRequest,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: ParticipationService = Depends(get_participation_service),
):
    return await service.record_event(payload, data)


@participation_router.get("/events/me", response_model=list[ParticipationEventItem])
async def my_events(
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: ParticipationService = Depends(get_participation_service),
):
    return await service.my_events(payload)
