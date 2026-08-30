from app.exceptions import AppException


class ParticipationEventNotFoundError(AppException):
    status_code = 404
    message = "Participation event not found"


class ExposureArmRequiredError(AppException):
    status_code = 422
    message = "A nudge_* event needs an arm_ref, or an experiment would measure self-selection rather than the nudge"


class ExposureArmNotAllowedError(AppException):
    status_code = 422
    message = "arm_ref is only meaningful on nudge_* events"
