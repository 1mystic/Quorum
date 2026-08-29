from app.core.database import get_db
from fastapi import Depends, Security
from sqlalchemy.ext.asyncio import AsyncSession
from app.repository import (
    UserRepository, CollegeRepository, StudentRepository, ClubRepository, MembershipRepository,
    EventRepository, EventRegistrationRepository, AnnouncementRepository, IssueRepository,
    NotificationRepository, CertificateRepository, LeaderboardRepository
)
from app.services import (
    UserService, CollegeService, StudentService, ClubService, MembershipService,
    EventService, EventRegistrationService, AnnouncementService, IssueService,
    NotificationService, CertificateService, LeaderboardService
)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, SecurityScopes
from app.core.token import decode_token
from app.core.storage import Storage, storage
from app.exceptions import AuthorizationError

def get_storage() -> Storage:
    return storage

def get_user_service(db: AsyncSession = Depends(get_db)):
    user_repo = UserRepository(db)
    college_repo = CollegeRepository(db)
    return UserService(user_repo, college_repo)

security = HTTPBearer()
def get_user_info(scopes: SecurityScopes, credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_token(credentials.credentials)
    if payload.get("role") not in scopes.scopes:
        raise AuthorizationError()
    return payload
            
def get_college_service(db: AsyncSession = Depends(get_db)):
    college_repo = CollegeRepository(db)
    user_repo = UserRepository(db)
    return CollegeService(college_repo, user_repo)

def get_student_service(db: AsyncSession = Depends(get_db),
                        storage: Storage = Depends(get_storage)):
    student_repo = StudentRepository(db)
    user_repo = UserRepository(db)
    membership_repo = MembershipRepository(db)
    return StudentService(student_repo, user_repo, membership_repo, storage)

def get_club_service(db: AsyncSession = Depends(get_db),
                     storage: Storage = Depends(get_storage)):
    club_repo = ClubRepository(db)
    student_repo = StudentRepository(db)
    user_repo = UserRepository(db)
    membership_repo = MembershipRepository(db)
    return ClubService(club_repo, student_repo, user_repo, membership_repo, storage)

def get_membership_service(db: AsyncSession = Depends(get_db)):
    membership_repo = MembershipRepository(db)
    club_repo = ClubRepository(db)
    student_repo = StudentRepository(db)
    notification_repo = NotificationRepository(db)
    return MembershipService(membership_repo, club_repo, student_repo, notification_repo)

def get_event_service(db: AsyncSession = Depends(get_db),
                      storage: Storage = Depends(get_storage)):
    event_repo = EventRepository(db)
    registration_repo = EventRegistrationRepository(db)
    club_repo = ClubRepository(db)
    membership_repo = MembershipRepository(db)
    student_repo = StudentRepository(db)
    user_repo = UserRepository(db)
    return EventService(event_repo, registration_repo, club_repo, membership_repo,
                        student_repo, user_repo, storage)

def get_event_registration_service(db: AsyncSession = Depends(get_db)):
    registration_repo = EventRegistrationRepository(db)
    event_repo = EventRepository(db)
    club_repo = ClubRepository(db)
    membership_repo = MembershipRepository(db)
    student_repo = StudentRepository(db)
    user_repo = UserRepository(db)
    notification_repo = NotificationRepository(db)
    return EventRegistrationService(registration_repo, event_repo, club_repo, membership_repo,
                                    student_repo, user_repo, notification_repo, db)

def get_announcement_service(db: AsyncSession = Depends(get_db)):
    announcement_repo = AnnouncementRepository(db)
    club_repo = ClubRepository(db)
    membership_repo = MembershipRepository(db)
    student_repo = StudentRepository(db)
    user_repo = UserRepository(db)
    return AnnouncementService(announcement_repo, club_repo, membership_repo,
                               student_repo, user_repo)

def get_issue_service(db: AsyncSession = Depends(get_db)):
    issue_repo = IssueRepository(db)
    club_repo = ClubRepository(db)
    event_repo = EventRepository(db)
    membership_repo = MembershipRepository(db)
    student_repo = StudentRepository(db)
    user_repo = UserRepository(db)
    return IssueService(issue_repo, club_repo, event_repo, membership_repo,
                        student_repo, user_repo)

def get_notification_service(db: AsyncSession = Depends(get_db)):
    notification_repo = NotificationRepository(db)
    student_repo = StudentRepository(db)
    return NotificationService(notification_repo, student_repo)

def get_certificate_service(db: AsyncSession = Depends(get_db),
                            storage: Storage = Depends(get_storage)):
    certificate_repo = CertificateRepository(db)
    student_repo = StudentRepository(db)
    notification_repo = NotificationRepository(db)
    return CertificateService(certificate_repo, student_repo, notification_repo, storage)

def get_leaderboard_service(db: AsyncSession = Depends(get_db)):
    leaderboard_repo = LeaderboardRepository(db)
    user_repo = UserRepository(db)
    return LeaderboardService(leaderboard_repo, user_repo)


    
# token -> decode -> authorization karenge -> role match -> user data return (token vala vhi jo diye the)

# onboardinig