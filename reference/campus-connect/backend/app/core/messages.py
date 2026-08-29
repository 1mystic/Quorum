class AuthMessages:
    SIGNUP_SUCCESS = "Account created successfully"
    LOGIN_SUCCESS = "Logged in successfully"
    RESET_LINK_SENT = "If that email is registered, a password reset link has been sent to it"
    PASSWORD_RESET = "Password reset successfully, please log in with your new password"
    GOOGLE_SIGNUP_SUCCESS = "Account created with Google successfully"
    GOOGLE_LOGIN_SUCCESS = "Logged in with Google successfully"


class CollegeMessages:
    ONBOARDED = "College onboarded successfully"


class StudentMessages:
    PROFILE_UPDATED = "Profile updated successfully"


class ClubMessages:
    CREATED_ACTIVE = "Club created and is now live"
    CREATED_PENDING = "Club submitted for admin approval"
    UPDATED = "Club updated successfully"
    ARCHIVED = "Club archived successfully"
    APPROVED = "Club approved"
    REJECTED = "Club rejected"
    STATUS_NEEDS_ROLE = (
        "status must be sent together with role: it means the club status for LEADER "
        "and your membership status for MEMBER"
    )


class MembershipMessages:
    JOIN_REQUESTED = "Join request sent"
    REQUEST_APPROVED = "Join request approved"
    REQUEST_REJECTED = "Join request rejected"
    MEMBER_REMOVED = "Member removed from the club"
    LEFT_CLUB = "You have left the club"


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


class IssueMessages:
    RAISED = "Issue submitted to the club leader"
    REPLIED = "Reply sent to the student"
    RESOLVED = "Issue marked as resolved"


class NotificationMessages:
    MARKED_READ = "Notification marked as read"
    ALL_MARKED_READ = "All notifications marked as read"

    @staticmethod
    def join_approved(club_name: str) -> str:
        return f"Your request to join {club_name} was approved"

    @staticmethod
    def join_rejected(club_name: str) -> str:
        return f"Your request to join {club_name} was not approved"

    @staticmethod
    def registration_confirmed(event_title: str) -> str:
        return f"You are registered for {event_title}"

    @staticmethod
    def result_posted(event_title: str, result: str) -> str:
        return f"Your result for {event_title} is now available: {result}"

    @staticmethod
    def certificate_issued(event_title: str) -> str:
        return f"Your certificate for {event_title} is ready to download"
