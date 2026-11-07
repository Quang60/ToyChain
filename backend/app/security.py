import base64
import hashlib
import hmac
import os
from datetime import timedelta
import jwt
from .db import utcnow


def hash_password(password):
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return base64.b64encode(salt + digest).decode()


def check_password(password, stored):
    raw = base64.b64decode(stored)
    digest = hashlib.scrypt(password.encode(), salt=raw[:16], n=16384, r=8, p=1)
    return hmac.compare_digest(digest, raw[16:])


def token_for(user, settings):
    return jwt.encode({"sub": user.id, "exp": utcnow() + timedelta(hours=8), "iss": "toychain"}, settings.jwt_secret, algorithm="HS256")
