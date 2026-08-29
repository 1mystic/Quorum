from app.schemas.user import (
    SignupRequest, SignupResponse, LoginRequest, LoginResponse,
    ForgotPasswordRequest, ForgotPasswordResponse, ResetPasswordRequest, ResetPasswordResponse,
    GoogleAuthRequest, GoogleAuthResponse
)
from app.schemas.college import CollegeOnboardingRequest, CollegeOnboardingResponse
from app.schemas.student import (
    StudentClubItem, PublicStudentResponse, StudentProfileResponse,
    UpdateProfileRequest, UpdateProfileResponse
)
from app.schemas.club import (
    ClubLinkSchema, CreateClubRequest, UpdateClubRequest, CreateClubResponse,
    ClubStatusResponse, ClubListItem, ClubDetailResponse, ClubHeadInfo, MyClubItem,
    TrendingClubItem
)
from app.schemas.membership import (
    JoinResponse, RequestActionRequest, RequestActionResponse, PendingRequestItem, MemberItem,
    RemoveMemberResponse
)
from app.schemas.event import (
    CreateEventRequest, UpdateEventRequest, CreateEventResponse, EventStatusResponse,
    EventListItem, EventDetailResponse
)
from app.schemas.event_registration import (
    RegistrationConfirmation, UnregisterResponse, ParticipantItem, MarkAttendanceRequest,
    AttendanceResponse, DeclareResultsRequest, DeclaredResultItem, DeclareResultsResponse,
    MyRegistrationItem, MyResultItem
)
from app.schemas.announcement import (
    CreateAnnouncementRequest, PinAnnouncementRequest, CreateAnnouncementResponse,
    AnnouncementItem, PinAnnouncementResponse, DeleteAnnouncementResponse,
    UnreadCountResponse, MarkAnnouncementsReadResponse
)
from app.schemas.issue import (
    RaiseIssueRequest, ReplyIssueRequest, RaiseIssueResponse, IssueResponseInfo,
    MyIssueItem, LeaderIssueItem, IssueActionResponse, OpenIssueCountResponse
)
from app.schemas.notification import (
    NotificationItem, NotificationCountResponse, NotificationReadResponse,
    MarkAllNotificationsReadResponse
)
from app.schemas.certificate import (
    MyCertificateItem, CertificateDownloadResponse, CertificateVerification
)
from app.schemas.leaderboard import LeaderboardEntry
from app.schemas.ai import ChatMessage, AgentChatRequest, AgentChatResponse
