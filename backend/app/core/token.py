from jose import jwt, ExpiredSignatureError, JWTError
from datetime import datetime, timezone, timedelta
from app.exceptions import AuthenticationError
from app.core.config import settings

    
def create_access_token(payload: dict, expires_minutes: int = 40000) -> str:
    iat = datetime.now(timezone.utc)
    expire = iat + timedelta(minutes=expires_minutes)
    to_encode = {**payload, "iat": iat, "exp": expire, "type": "access"}
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, settings.JWT_ALGORITHM)


def create_refresh_token(payload: dict, expires_days: int = 7) -> str:
    iat = datetime.now(timezone.utc)
    expire = iat + timedelta(days=expires_days)
    to_encode = {
        **payload,
        "iat": iat,
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, settings.JWT_ALGORITHM)

def create_reset_token(payload: dict, expires_minutes: int = 15) -> str:
    iat = datetime.now(timezone.utc)
    expire = iat + timedelta(minutes=expires_minutes)
    to_encode = {**payload, "iat": iat, "exp": expire, "type": "reset"}
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, settings.JWT_ALGORITHM)


def decode_token(token: str, exp_type: str = "access") -> dict:
    try:
        payload = jwt.decode(
            token=token,
            key=settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("type") != exp_type:
            raise AuthenticationError()
        return payload
    except ExpiredSignatureError:
        raise AuthenticationError()
    except JWTError as e:
        raise AuthenticationError()
        
    