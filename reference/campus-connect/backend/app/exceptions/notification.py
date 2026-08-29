from app.exceptions import AppException


class NotificationNotFoundError(AppException):
    status_code = 404
    message = "Notification not found"
