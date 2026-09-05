from app.repository import TenantRepository, UserRepository
from app.exceptions import TenantAlreadyExistError, TenantNotFoundError
from app.schemas import TenantOnboardingRequest, TenantOnboardingResponse, TenantInfoResponse
from app.core.messages import TenantMessages
from app.verticals import get_manifest


class TenantService:
    def __init__(self, tenant_repo: TenantRepository, user_repo: UserRepository):
        self.tenant_repo = tenant_repo
        self.user_repo = user_repo

    async def onboarding(self, payload: dict, data: TenantOnboardingRequest):
        # Raises VerticalNotFoundError if the manifest does not exist - fail fast
        # rather than create a tenant with no configuration to fall back to.
        manifest = get_manifest(data.vertical)

        is_exist = await self.tenant_repo.is_tenant_exist(data.slug)
        if is_exist:
            raise TenantAlreadyExistError()

        user_id = int(payload.get("sub"))

        new_tenant = await self.tenant_repo.create_tenant(
            name=data.name,
            slug=data.slug,
            vertical=data.vertical,
            description=data.description,
        )
        new_tenant.enabled_packs = list(manifest.default_packs)
        await self.user_repo.update_user(id=user_id, tenant_id=new_tenant.id)

        return TenantOnboardingResponse(
            name=new_tenant.name,
            slug=new_tenant.slug,
            vertical=new_tenant.vertical,
            description=new_tenant.description,
            message=TenantMessages.ONBOARDED,
        )

    async def get_info(self, tenant_id: int) -> TenantInfoResponse:
        """Called under /api/t/{slug}/tenant, after verify_tenant_scope has
        already matched the URL slug to the caller's JWT claim - tenant_id
        here is trusted, not re-derived from the URL. A 404 here means the
        tenant behind an otherwise-valid token no longer exists (deleted
        after the token was issued), not a lookup by an attacker-controlled
        slug."""
        tenant = await self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise TenantNotFoundError()

        return TenantInfoResponse(
            name=tenant.name,
            slug=tenant.slug,
            vertical=tenant.vertical,
            description=tenant.description,
            enabled_packs=tenant.enabled_packs,
            timezone=tenant.timezone,
        )
