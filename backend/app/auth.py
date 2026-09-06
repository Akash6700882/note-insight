"""Authentication dependency.

The backend NEVER trusts a user id sent in a request body. It reads the Firebase
ID token from the Authorization header, verifies it with the Admin SDK, and
derives the uid from the verified token. That uid is the only identity we use.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth

_bearer = HTTPBearer(auto_error=False)


async def get_current_uid(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token.",
        )
    try:
        decoded = firebase_auth.verify_id_token(creds.credentials)
    except Exception:  # invalid / expired / malformed token
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
        )
    return decoded["uid"]
