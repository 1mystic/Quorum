from fastapi import APIRouter, Depends, Security

from app.schemas import CreateDecisionRequest, DecisionItem, CastBallotRequest, BallotItem
from app.services import DecisionService
from app.core.di import get_decision_service, get_user_info

decision_router = APIRouter(prefix="/decisions", tags=["Decisions"])


@decision_router.post("", response_model=DecisionItem)
async def create_decision(
    data: CreateDecisionRequest,
    payload: dict = Security(get_user_info, scopes=["MEMBER", "TENANT_ADMIN"]),
    service: DecisionService = Depends(get_decision_service),
):
    return await service.create_decision(payload, data)


@decision_router.get("", response_model=list[DecisionItem])
async def list_decisions(
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: DecisionService = Depends(get_decision_service),
):
    return await service.list_decisions(payload)


@decision_router.get("/{decision_id}", response_model=DecisionItem)
async def get_decision(
    decision_id: int,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: DecisionService = Depends(get_decision_service),
):
    return await service.get_decision(payload, decision_id)


@decision_router.patch("/{decision_id}/close", response_model=DecisionItem)
async def close_decision(
    decision_id: int,
    payload: dict = Security(get_user_info, scopes=["MEMBER", "TENANT_ADMIN"]),
    service: DecisionService = Depends(get_decision_service),
):
    return await service.close_decision(payload, decision_id)


@decision_router.post("/{decision_id}/ballots", response_model=BallotItem)
async def cast_ballot(
    decision_id: int,
    data: CastBallotRequest,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: DecisionService = Depends(get_decision_service),
):
    return await service.cast_ballot(payload, decision_id, data)
