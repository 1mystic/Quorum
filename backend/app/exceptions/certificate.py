from app.exceptions import AppException


class CertificateNotFoundError(AppException):
    status_code = 404
    message = "Certificate not found"


class CertificateNotEarnedError(AppException):
    status_code = 400
    message = "No certificate has been issued for this registration"


class CertificateGenerationError(AppException):
    status_code = 500
    message = "The certificate could not be generated"
