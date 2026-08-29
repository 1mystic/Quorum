from fastapi import APIRouter, BackgroundTasks, Depends
from app.schemas import (
    SignupResponse, SignupRequest, LoginResponse, LoginRequest,
    ForgotPasswordRequest, ForgotPasswordResponse, ResetPasswordRequest, ResetPasswordResponse,
    GoogleAuthRequest, GoogleAuthResponse
)
from app.services import UserService
from app.core.di import get_user_service

auth_router = APIRouter(prefix="/auth", tags=["Auth"])

@auth_router.post("/signup", response_model=SignupResponse)
async def signup(data: SignupRequest, service: UserService = Depends(get_user_service)):
    return await service.signup(data)

@auth_router.post("/login", response_model=LoginResponse)
async def login(data:LoginRequest, service: UserService = Depends(get_user_service)):
    return await service.login(data)

@auth_router.post("/google", response_model=GoogleAuthResponse)
async def google_auth(data: GoogleAuthRequest, service: UserService = Depends(get_user_service)):
    return await service.google_auth(data)

@auth_router.post("/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(data: ForgotPasswordRequest, background: BackgroundTasks,
                          service: UserService = Depends(get_user_service)):
    return await service.forgot_password(data, background)

@auth_router.post("/reset-password", response_model=ResetPasswordResponse)
async def reset_password(data: ResetPasswordRequest,
                         service: UserService = Depends(get_user_service)):
    return await service.reset_password(data)

