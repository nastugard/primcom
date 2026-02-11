from __future__ import annotations

import hashlib


def sha256_text(value: str) -> str:
    h = hashlib.sha256()
    h.update(value.encode("utf-8"))
    return h.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
