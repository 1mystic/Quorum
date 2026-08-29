from app.exceptions import AppException


class AnnouncementNotFoundError(AppException):
    status_code = 404
    message = "Announcement not found"
