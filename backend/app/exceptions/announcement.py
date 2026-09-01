from app.exceptions import AppException


class AnnouncementNotFoundError(AppException):
    status_code = 404
    message = "Announcement not found"


class AnnouncementActionNotAllowedError(AppException):
    status_code = 403
    message = "This action is not allowed for this announcement"
