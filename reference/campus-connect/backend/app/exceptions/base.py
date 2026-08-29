class AppException(Exception):
    status_code = 500
    message = "Something went wrong"

    def __init__(self, message: str | None = None):
        self.message = message or self.message
        super().__init__(self.message)

