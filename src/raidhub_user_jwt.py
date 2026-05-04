from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

import httpx

from .config import Settings
from .linked_account_context import RAIDHUB_REQUEST_KEY, get_linked_account_redis
from .log import raidhub_api

_USER_JWT_KEY_PREFIX = "raidhub:discord:user_jwt"


def _destiny_ids_fingerprint(destiny_membership_ids: list[str]) -> str:
    normalized = sorted({str(x).strip() for x in destiny_membership_ids if str(x).strip()})
    raw = json.dumps(normalized, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _user_jwt_cache_key(settings: Settings, bungie_membership_id: str, destiny_ids: list[str]) -> str:
    ns = settings.raidhub_discord_linked_account_cache_ns.strip() or "1"
    fp = _destiny_ids_fingerprint(destiny_ids)
    return f"{_USER_JWT_KEY_PREFIX}:{ns}:{bungie_membership_id}:{fp}"


def _parse_expires_seconds(expires_iso: str) -> int | None:
    s = expires_iso.strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = (dt - datetime.now(tz=timezone.utc)).total_seconds()
        return int(delta) if delta > 120 else None
    except ValueError:
        return None


async def resolve_user_bearer_token(interaction: dict[str, Any], settings: Settings) -> str | None:
    """
    Mint (or reuse from Redis) a RaidHub user JWT via ``POST /authorize/user``, same as the Website.

    Requires ``RAIDHUB_CLIENT_SECRET`` and a linked Turso profile (``_raidhubRequest`` filled by
    ``attach_raidhub_linked_account_context``). Sends JWT to the API as ``x-raidhub-user-authorization``
    so ``Authorization: Discord …`` can coexist on the same request.
    """
    secret = settings.raidhub_client_secret.strip()
    if not secret:
        return None

    ctx = interaction.get(RAIDHUB_REQUEST_KEY) or {}
    bungie = ctx.get("bungieMembershipId")
    dest = ctx.get("destinyMembershipIds") or []
    if not bungie or not isinstance(dest, list) or not dest:
        return None

    bungie_str = str(bungie).strip()
    dest_strs = [str(x).strip() for x in dest if str(x).strip()]
    if not bungie_str or not dest_strs:
        return None

    cache_key = _user_jwt_cache_key(settings, bungie_str, dest_strs)
    r = get_linked_account_redis()
    if r is not None:
        try:
            cached = await r.get(cache_key)
            if cached:
                return str(cached).strip() or None
        except Exception as err:
            raidhub_api.warn("REDIS_USER_JWT_CACHE_GET_FAILED", err, {"key": cache_key})

    base = settings.raidhub_api_base_url.rstrip("/")
    body = {
        "bungieMembershipId": bungie_str,
        "destinyMembershipIds": dest_strs,
        "clientSecret": secret,
    }
    try:
        async with httpx.AsyncClient(base_url=base, timeout=20) as client:
            res = await client.post("/authorize/user", json=body)
    except httpx.RequestError as err:
        raidhub_api.warn("RAIDHUB_AUTHORIZE_USER_FAILED", err, {"bungie": bungie_str})
        return None

    if not res.is_success:
        raidhub_api.warn(
            "RAIDHUB_AUTHORIZE_USER_HTTP",
            None,
            {"status": res.status_code, "bungie": bungie_str, "body": res.text[:300]},
        )
        return None

    try:
        data = res.json()
    except Exception:
        return None

    token = str(data.get("value") or "").strip()
    if not token:
        return None

    ex = settings.raidhub_user_jwt_cache_ttl_seconds
    if isinstance(data.get("expires"), str):
        parsed = _parse_expires_seconds(data["expires"])
        if parsed is not None:
            ex = min(ex, parsed)

    if r is not None:
        try:
            await r.set(cache_key, token, ex=max(60, int(ex)))
        except Exception as err:
            raidhub_api.warn("REDIS_USER_JWT_CACHE_SET_FAILED", err, {"key": cache_key})

    return token
