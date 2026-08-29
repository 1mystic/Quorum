from app.exceptions import AppException


class IssueNotFoundError(AppException):
    status_code = 404
    message = "Issue not found"


class IssueActionNotAllowedError(AppException):
    status_code = 403
    message = "This action is not allowed for this issue"
