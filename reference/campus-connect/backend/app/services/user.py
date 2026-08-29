from fastapi import BackgroundTasks
from app.schemas import (
    SignupRequest, SignupResponse, LoginRequest, LoginResponse,
    ForgotPasswordRequest, ForgotPasswordResponse, ResetPasswordRequest, ResetPasswordResponse,
    GoogleAuthRequest, GoogleAuthResponse
)
from app.repository import UserRepository, CollegeRepository
from app.exceptions import (
    UserAlreadyExistError, CollegeNotFoundError, CollegeAlreadyExistError,
    IncorrectCredentialError, AuthenticationError, EmailNotVerifiedError, AccountNotExistError
)
from app.utils.hashing import hash_password, verify_password, password_fingerprint
from app.models import UserRole, AuthProvider
from app.core.config import settings
from app.core.google import verify_google_id_token
from app.core.mailer import send_password_reset_job
from app.core.token import create_access_token, create_refresh_token, create_reset_token, decode_token
from app.core.messages import AuthMessages

RESET_TOKEN_MINUTES = 15

class UserService:
    def __init__(self, user_repo : UserRepository, college_repo: CollegeRepository):
        self.user_repo = user_repo
        self.college_repo = college_repo
        
    async def signup(self, data: SignupRequest):
        is_exist = await self.user_repo.is_email_exist(data.email)
        if is_exist:
            raise UserAlreadyExistError()
        
        hashed_password = hash_password(data.password)
        
        college = await self.college_repo.email_to_college(data.email)
        
        if college and data.role == UserRole.CAMPUS_ADMIN:
            raise CollegeAlreadyExistError()
        
        if data.role == UserRole.STUDENT and not college:
            raise CollegeNotFoundError()
        
        college_id = college.id if college else None
        new_user = await self.user_repo.create_user(
            full_name=data.full_name,
            email=data.email,
            hashed_password=hashed_password,
            role=data.role,
            college_id=college_id
        )
        payload = {
            "sub": str(new_user.id),
            "full_name": new_user.full_name,
            "email": new_user.email,
            "role": new_user.role
        }
        if data.role == UserRole.STUDENT:
            new_student = await self.user_repo.create_student(user_id=new_user.id)
            payload["college_slug"] = college.slug
        elif data.role == UserRole.CAMPUS_ADMIN:
            new_campus_admin = await self.user_repo.create_campus_admin(user_id=new_user.id)
            
        access_token = create_access_token(payload=payload)
        refresh_token = create_refresh_token(payload=payload)
        return SignupResponse(access_token=access_token, refresh_token=refresh_token, message=AuthMessages.SIGNUP_SUCCESS)
    
    async def login(self, data: LoginRequest):
        user = await self.user_repo.get_user_by_email(data.email)
        if not user:
            await self._reject_missing_account(data.email)

        if not user.hashed_password or not verify_password(data.password, user.hashed_password):
            raise IncorrectCredentialError()
        
        slug = await self.college_repo.id_to_slug(user.college_id) if user.college_id else None
        
        payload = {
            "sub": str(user.id),
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
            "college_slug": slug
        }
            
        access_token = create_access_token(payload=payload)
        refresh_token = create_refresh_token(payload=payload)
        return LoginResponse(access_token=access_token, refresh_token=refresh_token, message=AuthMessages.LOGIN_SUCCESS)

    async def google_auth(self, data: GoogleAuthRequest) -> GoogleAuthResponse:
        claims = await verify_google_id_token(data.id_token)

        if not claims.get("email_verified"):
            raise EmailNotVerifiedError()

        email = claims["email"].strip().lower()
        google_sub = claims["sub"]
        full_name = (claims.get("name") or email.split("@")[0]).strip()
        picture = claims.get("picture")

        user = await self.user_repo.get_user_by_email(email)

        if user:
            if not user.google_sub:
                await self.user_repo.link_google(user, google_sub, picture)
            is_new_user = False
            message = AuthMessages.GOOGLE_LOGIN_SUCCESS
        elif data.intent == "signup":
            college = await self.college_repo.email_to_college(email)
            role = UserRole.STUDENT if college else UserRole.CAMPUS_ADMIN
            college_id = college.id if college else None
            user = await self.user_repo.create_user(
                full_name=full_name,
                email=email,
                role=role,
                college_id=college_id,
                auth_provider=AuthProvider.GOOGLE,
                google_sub=google_sub,
                profile_image_url=picture,
            )
            if role == UserRole.STUDENT:
                await self.user_repo.create_student(user_id=user.id)
            else:
                await self.user_repo.create_campus_admin(user_id=user.id)
            is_new_user = True
            message = AuthMessages.GOOGLE_SIGNUP_SUCCESS
        else:
            await self._reject_missing_account(email)

        slug = await self.college_repo.id_to_slug(user.college_id) if user.college_id else None
        payload = {
            "sub": str(user.id),
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
            "college_slug": slug,
        }
        access_token = create_access_token(payload=payload)
        refresh_token = create_refresh_token(payload=payload)
        return GoogleAuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            is_new_user=is_new_user,
            message=message,
        )

    async def forgot_password(self, data: ForgotPasswordRequest,
                              background: BackgroundTasks | None = None) -> ForgotPasswordResponse:
        user = await self.user_repo.get_user_by_email(data.email)

        if user and user.hashed_password and background is not None:
            token = create_reset_token(
                payload={
                    "sub": str(user.id),
                    "email": user.email,
                    "pwd": password_fingerprint(user.hashed_password),
                },
                expires_minutes=RESET_TOKEN_MINUTES,
            )
            background.add_task(
                send_password_reset_job,
                user.email,
                user.full_name,
                self._reset_url(token),
                RESET_TOKEN_MINUTES,
            )

        return ForgotPasswordResponse(message=AuthMessages.RESET_LINK_SENT)

    async def reset_password(self, data: ResetPasswordRequest) -> ResetPasswordResponse:
        payload = decode_token(data.token, exp_type="reset")

        user = await self.user_repo.get_user_by_id(int(payload.get("sub")))
        if not user or payload.get("pwd") != password_fingerprint(user.hashed_password):
            raise AuthenticationError()

        await self.user_repo.set_password(user, hash_password(data.password))
        return ResetPasswordResponse(message=AuthMessages.PASSWORD_RESET)

    async def _reject_missing_account(self, email: str):
        college = await self.college_repo.email_to_college(email)
        if not college:
            raise CollegeNotFoundError()
        raise AccountNotExistError()

    @staticmethod
    def _reset_url(token: str) -> str:
        return f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?token={token}"
        
        
        
        
            
        
        
        
        
        