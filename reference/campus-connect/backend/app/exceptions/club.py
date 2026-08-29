from app.exceptions import AppException


class ClubNotFoundError(AppException):
    status_code = 404
    message = "Club not found"


class ClubNotActiveError(AppException):
    status_code = 403
    message = "Club is not active"


class NotClubLeaderError(AppException):
    status_code = 403
    message = "Only the club leader can perform this action"


class AlreadyMemberError(AppException):
    status_code = 409
    message = "You already have a membership or request for this club"


class MembershipNotFoundError(AppException):
    status_code = 404
    message = "Membership request not found"


class ClubActionNotAllowedError(AppException):
    status_code = 403
    message = "This action is not allowed"


class InvalidStatusFilterError(AppException):
    status_code = 422
    message = "Invalid status filter"


class StudentNotFoundError(AppException):
    status_code = 404
    message = "Student profile not found"
