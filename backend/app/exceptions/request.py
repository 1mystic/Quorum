from app.exceptions import AppException


class RequestNotFoundError(AppException):
    status_code = 404
    message = "Request not found"


class RequestActionNotAllowedError(AppException):
    status_code = 403
    message = "This action is not allowed for this request"


class RequestCategoryInvalidError(AppException):
    status_code = 422
    message = "This category is not part of this tenant's vocabulary"


class RequestAlreadyTerminalError(AppException):
    status_code = 409
    message = "This request already reached a terminal state"


class RequestNotTerminalError(AppException):
    status_code = 409
    message = "This request has not reached a terminal state yet"


class RequestMergeTargetInvalidError(AppException):
    status_code = 422
    message = "A request cannot be merged into itself or into an already-merged request"
