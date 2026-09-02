from fastapi import APIRouter, Depends, Security

from app.schemas import RecordParticipationEventRequest, ParticipationEventItem
from app.services import ParticipationService
from app.core.di import get_participation_service, get_user_info

participation_router = APIRouter(prefix="/participation", tags=["Participation"])


# Stays MEMBER-only: recording a participation event is a write done in the
# context of the acting member, not an oversight read, and widening a write
# route without a specific requirement to do so is out of this pass's scope.
@participation_router.post("/events", response_model=ParticipationEventItem)
async def record_event(
    data: RecordParticipationEventRequest,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: ParticipationService = Depends(get_participation_service),
):
    return await service.record_event(payload, data)


# Self-scoped (the caller's own participation history); stays MEMBER-only,
# same reasoning as notification.py's "my notifications".
@participation_router.get("/events/me", response_model=list[ParticipationEventItem])
async def my_events(
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: ParticipationService = Depends(get_participation_service),
):
    return await service.my_events(payload)
