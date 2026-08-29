from app.exceptions import AppException


class EventNotFoundError(AppException):
    status_code = 404
    message = "Event not found"


class EventActionNotAllowedError(AppException):
    status_code = 403
    message = "This action is not allowed for this event"


class EventNotPublishedError(AppException):
    status_code = 403
    message = "Event is not open for registration"


class EventFullError(AppException):
    status_code = 409
    message = "Event has reached its capacity"


class RegistrationClosedError(AppException):
    status_code = 403
    message = "Registration for this event is closed"


class AlreadyRegisteredError(AppException):
    status_code = 409
    message = "You are already registered for this event"


class RegistrationNotFoundError(AppException):
    status_code = 404
    message = "Registration not found"


class NotGroupMemberError(AppException):
    status_code = 403
    message = "Only approved group members can register for this event"


class AttendanceNotAllowedError(AppException):
    status_code = 403
    message = "Attendance can only be marked once the event has started"


class NotCheckedInError(AppException):
    status_code = 400
    message = "Result can only be set for attendees who were checked in"


class ResultsAlreadyDeclaredError(AppException):
    status_code = 409
    message = "Results for this event have already been declared and can no longer be changed"
