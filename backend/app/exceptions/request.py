from app.exceptions import AppException


class RequestNotFoundError(AppException):
    status_code = 404
    message = "Request not found"


class RequestActionNotAllowedError(AppException):
    status_code = 403
    message = "This action is not allowed for this request"
