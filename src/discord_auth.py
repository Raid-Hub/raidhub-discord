from __future__ import annotations

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey


def verify_discord_signature(public_key_hex: str, timestamp: str, raw_body: bytes, signature_hex: str) -> bool:
    if not public_key_hex:
        return False
    try:
        verify_key = VerifyKey(bytes.fromhex(public_key_hex))
        verify_key.verify(timestamp.encode("utf-8") + raw_body, bytes.fromhex(signature_hex))
        return True
    except (BadSignatureError, ValueError):
        return False
