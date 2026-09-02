from fastapi import APIRouter, Depends, Security

from app.schemas import (
    CreateDecisionRequest, DecisionItem, CastBallotRequest, BallotItem, DecisionActionResponse,
    RejectContentRequest,
)
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


@decision_router.patch("/{decision_id}/submit-for-review", response_model=DecisionActionResponse)
async def submit_decision_for_review(
    decision_id: int,
    payload: dict = Security(get_user_info, scopes=["MEMBER", "TENANT_ADMIN"]),
    service: DecisionService = Depends(get_decision_service),
):
    return await service.submit_for_review(payload, decision_id)


@decision_router.patch("/{decision_id}/approve", response_model=DecisionActionResponse)
async def approve_decision(
    decision_id: int,
    payload: dict = Security(get_user_info, scopes=["TENANT_ADMIN"]),
    service: DecisionService = Depends(get_decision_service),
):
    return await service.approve(payload, decision_id)


@decision_router.patch("/{decision_id}/reject", response_model=DecisionActionResponse)
async def reject_decision(
    decision_id: int,
    data: RejectContentRequest,
    payload: dict = Security(get_user_info, scopes=["TENANT_ADMIN"]),
    service: DecisionService = Depends(get_decision_service),
):
    return await service.reject(payload, decision_id, data.reason)


@decision_router.get("", response_model=list[DecisionItem])
async def list_decisions(
    payload: dict = Security(get_user_info, scopes=["MEMBER", "TENANT_ADMIN"]),
    service: DecisionService = Depends(get_decision_service),
):
    return await service.list_decisions(payload)


@decision_router.get("/{decision_id}", response_model=DecisionItem)
async def get_decision(
    decision_id: int,
    payload: dict = Security(get_user_info, scopes=["MEMBER", "TENANT_ADMIN"]),
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


# Casting a ballot is inherently self-scoped; a TENANT_ADMIN voting through
# this route on a member's behalf would be the bug, not the fix, so this
# stays MEMBER-only.
@decision_router.post("/{decision_id}/ballots", response_model=BallotItem)
async def cast_ballot(
    decision_id: int,
    data: CastBallotRequest,
    payload: dict = Security(get_user_info, scopes=["MEMBER"]),
    service: DecisionService = Depends(get_decision_service),
):
    return await service.cast_ballot(payload, decision_id, data)
