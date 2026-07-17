from __future__ import annotations

import itsdangerous

from ..config import config

_SALT = "npps4-webview-user-v1"


def _serializer() -> itsdangerous.URLSafeTimedSerializer:
    return itsdangerous.URLSafeTimedSerializer(config.get_secret_key(), salt=_SALT)


def dumps_user(user_id: int, *, purpose: str) -> str:
    return _serializer().dumps({"user_id": int(user_id), "purpose": str(purpose)})


def loads_user(token: str, *, purpose: str, max_age: int = 86400) -> int:
    try:
        payload = _serializer().loads(token, max_age=max_age)
    except itsdangerous.BadData as exc:
        raise ValueError("invalid or expired WebView token") from exc
    if not isinstance(payload, dict) or payload.get("purpose") != purpose:
        raise ValueError("invalid WebView token purpose")
    try:
        return int(payload["user_id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid WebView user id") from exc
