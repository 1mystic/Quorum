import bcrypt
import hashlib

FINGERPRINT_LENGTH = 16

def password_fingerprint(hashed: str) -> str:
    return hashlib.sha256(hashed.encode("utf-8")).hexdigest()[:FINGERPRINT_LENGTH]

def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))