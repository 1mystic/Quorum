from app.exceptions import AppException


class DecisionNotFoundError(AppException):
    status_code = 404
    message = "Decision not found"


class DecisionOptionNotFoundError(AppException):
    status_code = 404
    message = "Decision option not found"


class DecisionAlreadyClosedError(AppException):
    status_code = 409
    message = "This decision is closed and no longer accepts ballots"


class DeclaredRuleInvalidError(AppException):
    status_code = 422
    message = "declared_rule must be recorded before any ballot is cast and must be one of the declared voting rules"


class BallotShapeInvalidError(AppException):
    status_code = 422
    message = "This ballot's shape does not match the decision's declared ballot_style"


class BallotOptionInvalidError(AppException):
    status_code = 422
    message = "A ballot referenced an option that does not belong to this decision"


class DecisionActionNotAllowedError(AppException):
    status_code = 403
    message = "This action is not allowed for this decision"


class DecisionNotOpenError(AppException):
    status_code = 403
    message = "This decision is not open for voting"
