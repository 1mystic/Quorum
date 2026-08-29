from app.exceptions import AppException

class UserAlreadyExistError(AppException):
    status_code = 409
    message = "Email already registered"
    
class CollegeNotFoundError(AppException):
    status_code = 404
    message = "College not registered"
    
class AuthenticationError(AppException):
    status_code = 401
    message = "Invalid token"
    
class CollegeAlreadyExistError(AppException):
    status_code = 409
    message = "College already registered"
    
class IncorrectCredentialError(AppException):
    status_code = 401
    message = "Incorrect email or password"

class AccountNotExistError(AppException):
    status_code = 404
    message = "Account does not exist"
    
class AuthorizationError(AppException):
    status_code = 401
    message = "Invalid token"

class InvalidGoogleTokenError(AppException):
    status_code = 401
    message = "Invalid Google token"

class EmailNotVerifiedError(AppException):
    status_code = 403
    message = "Google account email is not verified"

class GoogleAuthNotConfiguredError(AppException):
    status_code = 503
    message = "Google sign-in is not configured"