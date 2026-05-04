from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from typing import Any

import redis.asyncio as aioredis
from libsql_client import create_client_sync

from .config import Settings
from .log import ingress

RAIDHUB_REQUEST_KEY = "_raidhubRequest"

_redis: aioredis.Redis | None = None


def get_linked_account_redis() -> aioredis.Redis | None:
    """Shared Redis client (linked-account cache + user JWT cache)."""
    return _redis


def _redis_key(settings: Settings, turso_url: str, discord_user_id: str) -> str:
    """Namespace + Turso fingerprint so cache bust / env changes stay isolated."""
    url_fp = hashlib.sha256(turso_url.encode("utf-8")).hexdigest()[:12]
    ns = settings.raidhub_discord_linked_account_cache_ns.strip() or "1"
    return f"raidhub:discord:linked:{ns}:{url_fp}:{discord_user_id}"


def _redis_configured(settings: Settings) -> bool:
    return bool(settings.redis_url.strip()) or bool(settings.redis_host.strip())


async def init_linked_account_redis(settings: Settings) -> None:
    global _redis
    if not _redis_configured(settings):
        ingress.info("REDIS_LINKED_ACCOUNT_CACHE_DISABLED", {"reason": "no_redis_host_or_url"})
        return
    try:
        if settings.redis_url.strip():
            client = aioredis.from_url(
                settings.redis_url.strip(),
                decode_responses=True,
                socket_connect_timeout=5.0,
            )
        else:
            client = aioredis.Redis(
                host=settings.redis_host.strip(),
                port=settings.redis_port,
                password=settings.redis_password.strip() or None,
                db=settings.redis_db,
                decode_responses=True,
                socket_connect_timeout=5.0,
            )
        await client.ping()
        _redis = client
        ingress.info("REDIS_LINKED_ACCOUNT_CACHE_READY", {})
    except Exception as err:
        _redis = None
        ingress.warn(
            "REDIS_LINKED_ACCOUNT_CACHE_INIT_FAILED",
            err,
            {"host": settings.redis_host, "has_url": bool(settings.redis_url.strip())},
        )


async def close_linked_account_redis() -> None:
    global _redis
    if _redis is None:
        return
    try:
        await _redis.aclose()
    except Exception as err:
        ingress.warn("REDIS_LINKED_ACCOUNT_CACHE_CLOSE_FAILED", err, None)
    finally:
        _redis = None


@dataclass(frozen=True, slots=True)
class _LinkedSnapshot:
    bungie_membership_id: str | None
    destiny_membership_ids: tuple[str, ...]


def discord_user_snowflake(interaction: dict[str, Any]) -> str:
    member = interaction.get("member") or {}
    user = member.get("user") if isinstance(member, dict) else None
    if not user:
        user = interaction.get("user") or {}
    return str((user or {}).get("id") or "").strip()


def _lookup_linked_sync(turso_url: str, discord_user_id: str) -> _LinkedSnapshot:
    client = create_client_sync(turso_url)
    try:
        rs = client.execute(
            """
            SELECT a.bungie_membership_id AS mid, dp.destiny_membership_id AS did
            FROM account AS a
            LEFT JOIN destiny_profile AS dp
                ON dp.bungie_membership_id = a.bungie_membership_id
            WHERE a.provider = 'discord' AND a.provider_account_id = ?
            """,
            [discord_user_id],
        )
    finally:
        client.close()

    rows = list(rs.rows)
    if not rows:
        return _LinkedSnapshot(bungie_membership_id=None, destiny_membership_ids=())

    mids = {str(r[0]).strip() for r in rows if r[0] is not None and str(r[0]).strip()}
    bungie = next(iter(mids), None) if mids else None

    destiny: set[str] = set()
    for r in rows:
        if r[1] is None:
            continue
        s = str(r[1]).strip()
        if s:
            destiny.add(s)

    return _LinkedSnapshot(
        bungie_membership_id=bungie,
        destiny_membership_ids=tuple(sorted(destiny)),
    )


def _snapshot_to_json(snap: _LinkedSnapshot) -> str:
    return json.dumps(
        {
            "bungieMembershipId": snap.bungie_membership_id,
            "destinyMembershipIds": list(snap.destiny_membership_ids),
        },
        separators=(",", ":"),
    )


def _snapshot_from_json(raw: str) -> _LinkedSnapshot | None:
    try:
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            return None
        mid = obj.get("bungieMembershipId")
        dids = obj.get("destinyMembershipIds")
        bungie = str(mid).strip() if mid is not None else None
        bungie = bungie or None
        if not isinstance(dids, list):
            dids = []
        out = tuple(sorted({str(x).strip() for x in dids if str(x).strip()}))
        return _LinkedSnapshot(bungie_membership_id=bungie, destiny_membership_ids=out)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


async def attach_raidhub_linked_account_context(
    interaction: dict[str, Any], settings: Settings
) -> None:
    """
    Proxy-only: resolve Discord → RaidHub user from Turso (Website NextAuth DB).

    Mutates ``interaction[RAIDHUB_REQUEST_KEY]`` with:
    - ``discordUserId``: str | None
    - ``bungieMembershipId``: str | None
    - ``destinyMembershipIds``: list[str]

    When Redis is configured (same deployment style as RaidHub-Services: ``REDIS_HOST`` /
    ``REDIS_PORT`` / optional ``REDIS_PASSWORD`` or ``REDIS_URL``), results are cached with TTL.

    **Cache bust:** bump env ``RAIDHUB_DISCORD_LINKED_ACCOUNT_CACHE_NS`` (e.g. ``1`` → ``2``), or
    ``DEL`` keys matching ``raidhub:discord:linked:<ns>:*`` (use ``SCAN`` in production).
    """
    uid = discord_user_snowflake(interaction)
    url = settings.raidhub_account_turso_url.strip()
    ttl = max(5, settings.raidhub_account_lookup_cache_ttl_seconds)

    ctx: dict[str, Any] = {
        "discordUserId": uid or None,
        "bungieMembershipId": None,
        "destinyMembershipIds": [],
    }
    interaction[RAIDHUB_REQUEST_KEY] = ctx

    if not url or not uid:
        return

    rkey = _redis_key(settings, url, uid)
    client = _redis

    if client is not None:
        try:
            cached = await client.get(rkey)
            if cached is not None:
                snap = _snapshot_from_json(cached)
                if snap is not None:
                    ctx["bungieMembershipId"] = snap.bungie_membership_id
                    ctx["destinyMembershipIds"] = list(snap.destiny_membership_ids)
                    return
        except Exception as err:
            ingress.warn(
                "REDIS_LINKED_ACCOUNT_CACHE_GET_FAILED",
                err,
                {"redis_key": rkey},
            )

    try:
        snap = await asyncio.to_thread(_lookup_linked_sync, url, uid)
    except Exception as err:
        ingress.warn(
            "RAIDHUB_ACCOUNT_TURSO_LOOKUP_FAILED",
            err,
            {"discord_user_id": uid},
        )
        return

    ctx["bungieMembershipId"] = snap.bungie_membership_id
    ctx["destinyMembershipIds"] = list(snap.destiny_membership_ids)

    if client is not None:
        try:
            await client.set(rkey, _snapshot_to_json(snap), ex=ttl)
        except Exception as err:
            ingress.warn(
                "REDIS_LINKED_ACCOUNT_CACHE_SET_FAILED",
                err,
                {"redis_key": rkey},
            )
