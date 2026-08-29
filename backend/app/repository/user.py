from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User, UserRole, AuthProvider, Member, TenantAdmin
from sqlalchemy import select, exists

class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def is_email_exist(self, email: str) -> bool:
        result = await self.db.execute(select(exists().where(User.email==email)))
        return result.scalar()

    async def create_user(self, full_name: str, email: str, role: UserRole, tenant_id: int | None,
                          hashed_password: str | None = None,
                          auth_provider: AuthProvider = AuthProvider.LOCAL,
                          google_sub: str | None = None,
                          profile_image_url: str | None = None) -> User:
        new_user = User(
            email=email,
            full_name=full_name,
            hashed_password=hashed_password,
            role=role,
            tenant_id=tenant_id,
            auth_provider=auth_provider,
            google_sub=google_sub,
            profile_image_url=profile_image_url,
        )
        self.db.add(new_user)
        await self.db.flush()
        return new_user

    async def link_google(self, user: User, google_sub: str,
                          profile_image_url: str | None = None) -> User:
        user.google_sub = google_sub
        if profile_image_url and not user.profile_image_url:
            user.profile_image_url = profile_image_url
        return user
    
    async def create_member(self, user_id: int, tenant_id: int) -> Member:
        new_member = Member(user_id=user_id, tenant_id=tenant_id)
        self.db.add(new_member)
        return new_member

    async def create_tenant_admin(self, user_id: int, tenant_id: int | None = None) -> TenantAdmin:
        new_tenant_admin = TenantAdmin(user_id=user_id, tenant_id=tenant_id)
        self.db.add(new_tenant_admin)
        return new_tenant_admin
    
    async def get_user_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email==email))
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: int) -> User | None:
        result = await self.db.execute(select(User).where(User.id==user_id))
        return result.scalar_one_or_none()

    async def set_password(self, user: User, hashed_password: str) -> User:
        user.hashed_password = hashed_password
        return user

    async def set_profile_image(self, user: User, profile_image_url: str) -> User:
        user.profile_image_url = profile_image_url
        return user

    async def get_tenant_id(self, user_id: int) -> int | None:
        result = await self.db.execute(select(User.tenant_id).where(User.id==user_id))
        return result.scalar_one_or_none()
    
    async def update_user(self, id: int, full_name: str | None = None, tenant_id: int | None = None, profile_image_url: str | None = None) -> User:
        result = await self.db.execute(select(User).where(User.id==id))
        user = result.scalar()
        
        if full_name:
            user.full_name = full_name
        if tenant_id:
            user.tenant_id = tenant_id
        if profile_image_url:
            user.profile_image_url = profile_image_url
            
        return user


