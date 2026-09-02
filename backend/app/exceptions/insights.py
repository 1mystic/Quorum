from app.exceptions import AppException


class InsightNotFoundError(AppException):
    """Unknown service id: not in the registry at all. docs/STATS_API.md section 5."""
    status_code = 404
    message = "Unknown insight service"


class PackNotFoundError(AppException):
    """Unknown pack id: not one of the four registered in app.stats.registry.PACKS."""
    status_code = 404
    message = "Unknown insight pack"


class PackDisabledError(AppException):
    """docs/STATS_API.md section 5: 409 with {"reason": "pack_disabled", "pack": "..."}."""
    status_code = 409
    message = "pack_disabled"

    def __init__(self, pack: str):
        super().__init__()
        self.extra = {"reason": "pack_disabled", "pack": pack}


class StreamUnavailableError(AppException):
    """409 with {"reason": "stream_unavailable", "stream": "..."}."""
    status_code = 409
    message = "stream_unavailable"

    def __init__(self, stream: str):
        super().__init__()
        self.extra = {"reason": "stream_unavailable", "stream": stream}
