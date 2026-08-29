from app.exceptions import AppException


class StorageError(AppException):
    status_code = 500
    message = "File storage is unavailable right now"


class StorageNotConfiguredError(StorageError):
    message = "File storage is not configured"


class InvalidFileTypeError(AppException):
    status_code = 400
    message = "This file type is not supported"


class FileTooLargeError(AppException):
    status_code = 413
    message = "The file is too large"
