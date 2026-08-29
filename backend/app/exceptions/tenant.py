from app.exceptions import AppException


class VerticalNotFoundError(AppException):
    status_code = 422
    message = "Unknown vertical"


class TenantSlugMismatchError(AppException):
    """
    The slug in the URL does not match the tenant_id claim in the caller's
    token. Never trust the URL alone - see docs/RULES.md section 5.
    """
    status_code = 403
    message = "Tenant mismatch"
