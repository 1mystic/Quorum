from fastapi import APIRouter, Depends, File, Form, Security, UploadFile
from app.schemas import (
    StudentProfileResponse, UpdateProfileRequest, UpdateProfileResponse, PublicStudentResponse
)
from app.services import StudentService
from app.core.di import get_student_service, get_user_info
from app.core.forms import parse_form_model

student_router = APIRouter(prefix="/students", tags=["Students"])


@student_router.get("/me", response_model=StudentProfileResponse)
async def my_profile(
    payload: dict = Security(get_user_info, scopes=["STUDENT"]),
    service: StudentService = Depends(get_student_service),
):
    return await service.my_profile(payload)


@student_router.patch("/me", response_model=UpdateProfileResponse)
async def update_my_profile(
    data: str | None = Form(None, description="JSON body of UpdateProfileRequest"),
    image: UploadFile | None = File(None),
    payload: dict = Security(get_user_info, scopes=["STUDENT"]),
    service: StudentService = Depends(get_student_service),
):
    parsed = parse_form_model(UpdateProfileRequest, data) if data is not None else UpdateProfileRequest()
    return await service.update_my_profile(payload, parsed, image)


@student_router.get("/{student_id}", response_model=PublicStudentResponse)
async def student_profile(
    student_id: int,
    payload: dict = Security(get_user_info, scopes=["STUDENT", "CAMPUS_ADMIN"]),
    service: StudentService = Depends(get_student_service),
):
    return await service.public_profile(payload, student_id)
