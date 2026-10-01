"""Demo authentication: PBKDF2 password hashes + JWT bearer tokens + role checks."""
import hashlib, hmac, os
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.config import get_settings
from app.database.session import get_db
from app.models.db import Customer

bearer = HTTPBearer(auto_error=False)
ITER = 60_000


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(12)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITER)
    return f"pbkdf2${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, dk = stored.split("$")
        cand = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITER).hex()
        return hmac.compare_digest(cand, dk)
    except Exception:
        return False


def create_token(user: Customer) -> str:
    s = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(minutes=s.jwt_expire_minutes)
    return jwt.encode({"sub": user.customer_id, "role": user.role, "exp": exp}, s.jwt_secret, algorithm="HS256")


def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer), db: Session = Depends(get_db)) -> Customer:
    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        payload = jwt.decode(creds.credentials, get_settings().jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = db.get(Customer, payload["sub"])
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown user")
    return user


def require_roles(*roles: str):
    def dep(user: Customer = Depends(current_user)) -> Customer:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient role")
        return user
    return dep


STAFF = ("SUPPORT_AGENT", "ADMIN")
