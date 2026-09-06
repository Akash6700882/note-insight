"""Firebase Admin initialisation.

One place initialises the Admin SDK. It gives us two things:
  * `verify_id_token` — trust the caller's identity (server-side, never the client's word)
  * `firestore.client()` — the database
"""
import json

import firebase_admin
from firebase_admin import credentials, firestore

from .config import settings


def _build_credentials() -> credentials.Base:
    if settings.firebase_credentials_json:
        return credentials.Certificate(json.loads(settings.firebase_credentials_json))
    if settings.firebase_credentials_path:
        return credentials.Certificate(settings.firebase_credentials_path)
    raise RuntimeError(
        "No Firebase credentials configured. Set FIREBASE_CREDENTIALS_PATH "
        "or FIREBASE_CREDENTIALS_JSON."
    )


if not firebase_admin._apps:
    firebase_admin.initialize_app(_build_credentials())

db = firestore.client()
