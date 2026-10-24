import hmac
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from backend.app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 12


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.APP_SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, settings.APP_SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def verify_meta_webhook_signature(payload_body: bytes, signature_header: Optional[str]) -> bool:
    """
    Validates X-Hub-Signature-256 from Meta WhatsApp Business Platform.
    Format: 'sha256=<hex_digest>'
    """
    if not settings.WHATSAPP_APP_SECRET:
        # If secret is not set in development mode, allow through with warning
        return True
    if not signature_header:
        return False
    
    parts = signature_header.split("=")
    if len(parts) != 2 or parts[0] != "sha256":
        return False
        
    expected_hash = parts[1]
    calculated_hash = hmac.new(
        key=settings.WHATSAPP_APP_SECRET.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_hash, calculated_hash)
