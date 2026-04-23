from __future__ import annotations

from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey


def _normalize_hex_header(raw: str) -> str:
    """
    Proxies can occasionally forward duplicate signature headers as a comma-separated list.
    Discord signs with a single value; use the first token and trim whitespace.
    """
    return raw.split(",", 1)[0].strip()


def verify_discord_signature_with_reason(
    public_key_hex: str,
    timestamp: str,
    raw_body: bytes,
    signature_hex: str,
) -> tuple[bool, str]:
    public_key_hex = _normalize_hex_header(public_key_hex)
    signature_hex = _normalize_hex_header(signature_hex)
    timestamp = timestamp.strip()

    if not public_key_hex:
        return False, "missing_public_key"
    if not signature_hex:
        return False, "missing_signature_header"
    if not timestamp:
        return False, "missing_timestamp_header"

    try:
        verify_key = VerifyKey(bytes.fromhex(public_key_hex))
        verify_key.verify(timestamp.encode("utf-8") + raw_body, bytes.fromhex(signature_hex))
        return True, "ok"
    except ValueError:
        # Invalid hex in public key or signature header.
        return False, "invalid_hex_header"
    except BadSignatureError:
        return False, "bad_signature"


def verify_discord_signature(
    public_key_hex: str,
    timestamp: str,
    raw_body: bytes,
    signature_hex: str,
) -> bool:
    ok, _ = verify_discord_signature_with_reason(
        public_key_hex, timestamp, raw_body, signature_hex
    )
    return ok
