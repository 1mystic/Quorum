# from app.schemas import 
from app.repository import CollegeRepository, UserRepository
from app.exceptions import UserAlreadyExistError, CollegeNotFoundError, CollegeAlreadyExistError, IncorrectCredentialError
from app.schemas import CollegeOnboardingRequest, CollegeOnboardingResponse
from app.core.messages import CollegeMessages

class CollegeService:
    def __init__(self, college_repo: CollegeRepository, user_repo: UserRepository):
        self.college_repo = college_repo
        self.user_repo = user_repo
    
    async def onboarding(self, payload: dict, data: CollegeOnboardingRequest):
        is_exist = await self.college_repo.is_college_exist(data.email_suffix)
        if is_exist:
            raise CollegeAlreadyExistError()
        
        user_id = int(payload.get("sub"))
        slug = data.email_suffix.split(".")[0]
        count = await self.college_repo.slug_count(slug)
        slug = slug if count == 0 else f"{slug}-{count+1}"
        
        new_college = await self.college_repo.create_college(
            name= data.name,
            email_suffix=data.email_suffix,
            slug=slug,
            description=data.description
        )
        await self.user_repo.update_user(id=user_id, college_id=new_college.id)
        
        return CollegeOnboardingResponse(
            name=new_college.name,
            slug=new_college.slug,
            email_suffix=new_college.email_suffix,
            description=new_college.description,
            message=CollegeMessages.ONBOARDED
        )
        
        
        
        