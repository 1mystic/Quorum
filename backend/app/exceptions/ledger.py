from app.exceptions import AppException


class DueNotFoundError(AppException):
    status_code = 404
    message = "Due not found"


class PaymentNotFoundError(AppException):
    status_code = 404
    message = "Payment not found"


class PaymentAlreadySettledError(AppException):
    status_code = 409
    message = "This payment was already verified and settled"


class DueAlreadySettledError(AppException):
    status_code = 409
    message = "This due was already settled (paid, waived or written off)"


class ReceiptAlreadyIssuedError(AppException):
    status_code = 409
    message = "A receipt was already issued for this payment"


class ReceiptNotFoundError(AppException):
    status_code = 404
    message = "Receipt not found"


class LedgerCategoryInvalidError(AppException):
    status_code = 422
    message = "This category is not part of this tenant's declared ledger vocabulary"
