from app.exceptions import AppException


class GroupNotFoundError(AppException):
    status_code = 404
    message = "Group not found"


class GroupNotActiveError(AppException):
    status_code = 403
    message = "Group is not active"


class NotGroupLeaderError(AppException):
    status_code = 403
    message = "Only the group leader can perform this action"


class AlreadyMemberError(AppException):
    status_code = 409
    message = "You already have a membership or request for this group"


class MembershipNotFoundError(AppException):
    status_code = 404
    message = "Membership request not found"


class GroupActionNotAllowedError(AppException):
    status_code = 403
    message = "This action is not allowed"


class InvalidStatusFilterError(AppException):
    status_code = 422
    message = "Invalid status filter"


class MemberNotFoundError(AppException):
    status_code = 404
    message = "Member profile not found"
