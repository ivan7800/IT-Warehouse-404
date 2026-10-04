import base64
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

PBKDF2_ITERATIONS = 310_000
SESSION_HOURS = int(os.environ.get('WAREHOUSE_SESSION_HOURS', '12'))


def utc_now():
    return datetime.now(timezone.utc)


def iso_utc(dt=None):
    return (dt or utc_now()).isoformat(timespec='seconds')


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError('La contraseña debe tener al menos 12 caracteres')
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, PBKDF2_ITERATIONS)
    return f'pbkdf2_sha256${PBKDF2_ITERATIONS}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}'


def verify_password(password: str, encoded: str) -> bool:
    try:
        alg, rounds, salt64, digest64 = encoded.split('$', 3)
        if alg != 'pbkdf2_sha256':
            return False
        salt = base64.urlsafe_b64decode(salt64.encode())
        expected = base64.urlsafe_b64decode(digest64.encode())
        actual = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, int(rounds))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def new_session_material():
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires = utc_now() + timedelta(hours=SESSION_HOURS)
    return token, token_hash, csrf, expires


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
