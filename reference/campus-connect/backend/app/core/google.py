import asyncio

from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.core.config import settings
from app.exceptions import InvalidGoogleTokenError, GoogleAuthNotConfiguredError

GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


def _verify(token: str) -> dict:
    if not settings.GOOGLE_CLIENT_ID:
        raise GoogleAuthNotConfiguredError()
    try:
        claims = id_token.verify_oauth2_token(
            token, google_requests.Request(), settings.GOOGLE_CLIENT_ID
        )
    except (ValueError, GoogleAuthError):
        raise InvalidGoogleTokenError()
    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise InvalidGoogleTokenError()
    return claims


async def verify_google_id_token(token: str) -> dict:
    return await asyncio.to_thread(_verify, token)
