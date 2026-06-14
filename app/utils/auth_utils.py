import os
import bcrypt
import jwt
from datetime import datetime, timedelta
from typing import Union, Any

SECRET_KEY = os.getenv("JWT_SECRET", "super_secret_xeno_crm_key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day expiration

def hash_password(password: str) -> str:
    """
    Hashes a clear text password using bcrypt.
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Checks a clear text password against its bcrypt hash.
    """
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    """
    Generates a secure JWT access token containing the subject.
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Union[str, None]:
    """
    Decodes a JWT access token and returns the subject if valid.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except Exception:
        return None
