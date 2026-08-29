from app.exceptions.base import AppException
from app.exceptions.user import (
    UserAlreadyExistError, TenantNotFoundError, AuthenticationError,
    TenantAlreadyExistError, IncorrectCredentialError, AuthorizationError,
    InvalidGoogleTokenError, EmailNotVerifiedError, GoogleAuthNotConfiguredError,
    AccountNotExistError
)
from app.exceptions.group import (
    GroupNotFoundError, GroupNotActiveError, NotGroupLeaderError, AlreadyMemberError,
    MembershipNotFoundError, GroupActionNotAllowedError, MemberNotFoundError,
    InvalidStatusFilterError, MembershipNotFoundError, GroupActionNotAllowedError, MemberNotFoundError
)
from app.exceptions.event import (
    EventNotFoundError, EventActionNotAllowedError, EventNotPublishedError, EventFullError,
    RegistrationClosedError, AlreadyRegisteredError, RegistrationNotFoundError,
    NotGroupMemberError, AttendanceNotAllowedError, NotCheckedInError,
    ResultsAlreadyDeclaredError
)
from app.exceptions.announcement import AnnouncementNotFoundError
from app.exceptions.request import RequestNotFoundError, RequestActionNotAllowedError
from app.exceptions.notification import NotificationNotFoundError
from app.exceptions.storage import (
    StorageError, StorageNotConfiguredError, InvalidFileTypeError, FileTooLargeError
)
from app.exceptions.certificate import (
    CertificateNotFoundError, CertificateNotEarnedError, CertificateGenerationError
)
from app.exceptions.tenant import VerticalNotFoundError, TenantSlugMismatchError