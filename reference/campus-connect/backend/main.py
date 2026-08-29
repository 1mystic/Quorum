import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from app.exceptions import AppException
from fastapi.responses import JSONResponse
from app.api import (
    auth_router, college_router, student_router, club_router, event_router, announcement_router,
    issue_router, notification_router, certificate_router, leaderboard_router, ai_router
)
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

@asynccontextmanager
async def lifespan(_: FastAPI):
    """Warm the LLM connection before the first student question arrives."""
    from app.agent import providers

    task = asyncio.create_task(providers.warm_up())
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(title="CampusConnect",
    description="Backend APIs for campusconnect.itshrestha.dev",
    lifespan=lifespan,
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(AppException)
async def handle_app_exc(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.message}
    )

app.include_router(auth_router)
app.include_router(college_router)
app.include_router(student_router)
app.include_router(club_router)
app.include_router(event_router)
app.include_router(announcement_router)
app.include_router(issue_router)
app.include_router(notification_router)
app.include_router(certificate_router)
app.include_router(leaderboard_router)
app.include_router(ai_router)
