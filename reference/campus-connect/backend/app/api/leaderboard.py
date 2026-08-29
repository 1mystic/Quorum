from fastapi import APIRouter, Depends, Security
from app.schemas import LeaderboardEntry
from app.services import LeaderboardService
from app.core.di import get_leaderboard_service, get_user_info

leaderboard_router = APIRouter(prefix="/leaderboard", tags=["Leaderboard"])


@leaderboard_router.get("", response_model=list[LeaderboardEntry])
async def leaderboard(
    payload: dict = Security(get_user_info, scopes=["STUDENT"]),
    service: LeaderboardService = Depends(get_leaderboard_service),
):
    return await service.get(payload)
