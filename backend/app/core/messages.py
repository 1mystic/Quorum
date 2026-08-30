class AuthMessages:
    SIGNUP_SUCCESS = "Account created successfully"
    LOGIN_SUCCESS = "Logged in successfully"
    RESET_LINK_SENT = "If that email is registered, a password reset link has been sent to it"
    PASSWORD_RESET = "Password reset successfully, please log in with your new password"
    GOOGLE_SIGNUP_SUCCESS = "Account created with Google successfully"
    GOOGLE_LOGIN_SUCCESS = "Logged in with Google successfully"


class TenantMessages:
    ONBOARDED = "Tenant onboarded successfully"


class MemberMessages:
    PROFILE_UPDATED = "Profile updated successfully"


class GroupMessages:
    CREATED_ACTIVE = "Group created and is now live"
    CREATED_PENDING = "Group submitted for admin approval"
    UPDATED = "Group updated successfully"
    ARCHIVED = "Group archived successfully"
    APPROVED = "Group approved"
    REJECTED = "Group rejected"
    STATUS_NEEDS_ROLE = (
        "status must be sent together with role: it means the group status for LEADER "
        "and your membership status for MEMBER"
    )


class MembershipMessages:
    JOIN_REQUESTED = "Join request sent"
    REQUEST_APPROVED = "Join request approved"
    REQUEST_REJECTED = "Join request rejected"
    MEMBER_REMOVED = "Member removed from the group"
    LEFT_GROUP = "You have left the group"


class EventMessages:
    CREATED = "Event created as a draft"
    UPDATED = "Event updated successfully"
    PUBLISHED = "Event published successfully"
    CANCELLED = "Event cancelled successfully"


class RegistrationMessages:
    REGISTERED = "Registered successfully"
    UNREGISTERED = "Registration cancelled"
    CHECKED_IN = "Attendance marked"
    CHECK_IN_UNDONE = "Attendance unmarked"
    RESULTS_DECLARED = "Results declared, certificates are being generated"


class AnnouncementMessages:
    POSTED = "Announcement posted successfully"
    PINNED = "Announcement pinned to the top of the feed"
    UNPINNED = "Announcement unpinned"
    DELETED = "Announcement deleted successfully"
    MARKED_READ = "All announcements marked as read"


class RequestMessages:
    RAISED = "Request submitted to the group leader"
    REPLIED = "Reply sent to the member"
    RESOLVED = "Request marked as resolved"
    ESCALATED = "Request escalated"
    WITHDRAWN = "Request withdrawn"
    ASSIGNED = "Request assigned"
    REASSIGNED = "Request reassigned"
    PAUSED = "Request paused"
    RESUMED = "Request resumed"
    MERGED = "Request merged"
    REOPENED = "Request reopened"


class NotificationMessages:
    MARKED_READ = "Notification marked as read"
    ALL_MARKED_READ = "All notifications marked as read"

    @staticmethod
    def join_approved(group_name: str) -> str:
        return f"Your request to join {group_name} was approved"

    @staticmethod
    def join_rejected(group_name: str) -> str:
        return f"Your request to join {group_name} was not approved"

    @staticmethod
    def registration_confirmed(event_title: str) -> str:
        return f"You are registered for {event_title}"

    @staticmethod
    def result_posted(event_title: str, result: str) -> str:
        return f"Your result for {event_title} is now available: {result}"

    @staticmethod
    def certificate_issued(event_title: str) -> str:
        return f"Your certificate for {event_title} is ready to download"
