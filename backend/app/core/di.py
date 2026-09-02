from app.core.database import get_db
from fastapi import Depends, Security
from sqlalchemy.ext.asyncio import AsyncSession
from app.repository import (
    UserRepository, TenantRepository, MemberRepository, GroupRepository, MembershipRepository,
    EventRepository, EventRegistrationRepository, AnnouncementRepository, RequestRepository,
    NotificationRepository, CertificateRepository, LedgerRepository, InsightRunRepository,
    ParticipationRepository, DecisionRepository
)
from app.services import (
    UserService, TenantService, MemberService, GroupService, MembershipService,
    EventService, EventRegistrationService, AnnouncementService, RequestService,
    NotificationService, CertificateService, LedgerService, InsightsService,
    ParticipationService, DecisionService
)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, SecurityScopes
from app.core.token import decode_token
from app.core.storage import Storage, storage
from app.core.tenancy import get_current_tenant_id
from app.exceptions import AuthorizationError

def get_storage() -> Storage:
    return storage

def get_user_service(db: AsyncSession = Depends(get_db)):
    user_repo = UserRepository(db)
    tenant_repo = TenantRepository(db)
    return UserService(user_repo, tenant_repo)

security = HTTPBearer()
def get_user_info(scopes: SecurityScopes, credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_token(credentials.credentials)
    if payload.get("role") not in scopes.scopes:
        raise AuthorizationError()
    return payload
            
def get_tenant_service(db: AsyncSession = Depends(get_db)):
    tenant_repo = TenantRepository(db)
    user_repo = UserRepository(db)
    return TenantService(tenant_repo, user_repo)

def get_member_service(db: AsyncSession = Depends(get_db),
                        storage: Storage = Depends(get_storage)):
    member_repo = MemberRepository(db)
    user_repo = UserRepository(db)
    membership_repo = MembershipRepository(db)
    return MemberService(member_repo, user_repo, membership_repo, storage)

def get_group_service(db: AsyncSession = Depends(get_db),
                     storage: Storage = Depends(get_storage)):
    group_repo = GroupRepository(db)
    member_repo = MemberRepository(db)
    user_repo = UserRepository(db)
    membership_repo = MembershipRepository(db)
    return GroupService(group_repo, member_repo, user_repo, membership_repo, storage)

def get_membership_service(db: AsyncSession = Depends(get_db)):
    membership_repo = MembershipRepository(db)
    group_repo = GroupRepository(db)
    member_repo = MemberRepository(db)
    notification_repo = NotificationRepository(db)
    return MembershipService(membership_repo, group_repo, member_repo, notification_repo)

def get_event_service(db: AsyncSession = Depends(get_db),
                      storage: Storage = Depends(get_storage)):
    event_repo = EventRepository(db)
    registration_repo = EventRegistrationRepository(db)
    group_repo = GroupRepository(db)
    membership_repo = MembershipRepository(db)
    member_repo = MemberRepository(db)
    user_repo = UserRepository(db)
    return EventService(event_repo, registration_repo, group_repo, membership_repo,
                        member_repo, user_repo, storage)

def get_event_registration_service(db: AsyncSession = Depends(get_db)):
    registration_repo = EventRegistrationRepository(db)
    event_repo = EventRepository(db)
    group_repo = GroupRepository(db)
    membership_repo = MembershipRepository(db)
    member_repo = MemberRepository(db)
    user_repo = UserRepository(db)
    notification_repo = NotificationRepository(db)
    return EventRegistrationService(registration_repo, event_repo, group_repo, membership_repo,
                                    member_repo, user_repo, notification_repo, db)

def get_announcement_service(db: AsyncSession = Depends(get_db)):
    announcement_repo = AnnouncementRepository(db)
    group_repo = GroupRepository(db)
    membership_repo = MembershipRepository(db)
    member_repo = MemberRepository(db)
    user_repo = UserRepository(db)
    return AnnouncementService(announcement_repo, group_repo, membership_repo,
                               member_repo, user_repo)

def get_request_service(db: AsyncSession = Depends(get_db),
                        tenant_id: int = Depends(get_current_tenant_id)):
    request_repo = RequestRepository(db, tenant_id)
    group_repo = GroupRepository(db)
    event_repo = EventRepository(db)
    membership_repo = MembershipRepository(db)
    member_repo = MemberRepository(db)
    user_repo = UserRepository(db)
    tenant_repo = TenantRepository(db)
    return RequestService(request_repo, group_repo, event_repo, membership_repo,
                        member_repo, user_repo, tenant_repo)

def get_notification_service(db: AsyncSession = Depends(get_db)):
    notification_repo = NotificationRepository(db)
    member_repo = MemberRepository(db)
    return NotificationService(notification_repo, member_repo)

def get_certificate_service(db: AsyncSession = Depends(get_db),
                            storage: Storage = Depends(get_storage)):
    certificate_repo = CertificateRepository(db)
    member_repo = MemberRepository(db)
    notification_repo = NotificationRepository(db)
    return CertificateService(certificate_repo, member_repo, notification_repo, storage)

def get_ledger_service(db: AsyncSession = Depends(get_db),
                       tenant_id: int = Depends(get_current_tenant_id)):
    ledger_repo = LedgerRepository(db, tenant_id)
    member_repo = MemberRepository(db)
    user_repo = UserRepository(db)
    tenant_repo = TenantRepository(db)
    return LedgerService(ledger_repo, member_repo, user_repo, tenant_repo)

def get_insights_service(db: AsyncSession = Depends(get_db),
                         tenant_id: int = Depends(get_current_tenant_id)):
    run_repo = InsightRunRepository(db, tenant_id)
    tenant_repo = TenantRepository(db)
    return InsightsService(run_repo, tenant_repo, db)

def get_participation_service(db: AsyncSession = Depends(get_db),
                              tenant_id: int = Depends(get_current_tenant_id)):
    participation_repo = ParticipationRepository(db, tenant_id)
    member_repo = MemberRepository(db)
    user_repo = UserRepository(db)
    tenant_repo = TenantRepository(db)
    return ParticipationService(participation_repo, member_repo, user_repo, tenant_repo)

def get_decision_service(db: AsyncSession = Depends(get_db),
                         tenant_id: int = Depends(get_current_tenant_id)):
    decision_repo = DecisionRepository(db, tenant_id)
    member_repo = MemberRepository(db)
    user_repo = UserRepository(db)
    tenant_repo = TenantRepository(db)
    membership_repo = MembershipRepository(db)
    group_repo = GroupRepository(db)
    return DecisionService(decision_repo, member_repo, user_repo, tenant_repo,
                           membership_repo, group_repo)



    
# token -> decode -> authorization karenge -> role match -> user data return (token vala vhi jo diye the)

# onboardinig