#!/usr/bin/env python3
"""
CrispASR TTS Web UI v3 — JWT Authentication
Hand-rolled JWT, zero external dependencies.
Only imports from config.
"""

import base64
import hashlib
import hmac
import json
import time

from . import config


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def jwt_encode(payload: dict) -> str:
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body = _b64url(json.dumps(payload).encode())
    sig = _b64url(
        hmac.new(
            config.JWT_SECRET.encode(),
            f"{header}.{body}".encode(),
            hashlib.sha256,
        ).digest()
    )
    return f"{header}.{body}.{sig}"


def jwt_decode(token: str) -> dict | None:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header, body, sig = parts
        expected = _b64url(
            hmac.new(
                config.JWT_SECRET.encode(),
                f"{header}.{body}".encode(),
                hashlib.sha256,
            ).digest()
        )
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_b64url_decode(body))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None
