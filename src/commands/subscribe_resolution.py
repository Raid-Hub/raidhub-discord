from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from ..raidhub_client import RaidHubClient

_CLAN_GROUP_ID_PATTERNS = (
    re.compile(r"(?:https?://)?(?:www\.)?raidhub\.io/clan/(\d+)", re.I),
    re.compile(r"(?:https?://)?(?:www\.)?bungie\.net/[^?\s]*[?&]group(?:id|Id)=(\d+)", re.I),
    re.compile(r"/GroupV2/(\d+)", re.I),
    re.compile(r"/clan/(\d+)", re.I),
)


def parse_clan_group_id(raw: str) -> str | None:
    s = raw.strip()
    if not s:
        return None
    if re.fullmatch(r"\d+", s):
        return s
    for pat in _CLAN_GROUP_ID_PATTERNS:
        m = pat.search(s)
        if m:
            return m.group(1)
    try:
        path = urlparse(s).path or ""
        for seg in reversed([p for p in path.split("/") if p]):
            if seg.isdigit() and len(seg) >= 5:
                return seg
    except Exception:
        pass
    return None


def _norm_membership_id(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s or not re.fullmatch(r"\d+", s):
        return None
    return str(int(s))


def bungie_emblem_url(icon_path: str | None) -> str | None:
    if not icon_path:
        return None
    path = icon_path.strip()
    if not path:
        return None
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"https://www.bungie.net{path}"


def format_player_display_name(player: dict[str, Any]) -> str:
    bungie = player.get("bungieGlobalDisplayName")
    if bungie:
        code = player.get("bungieGlobalDisplayNameCode")
        suffix = f"#{code}" if code else ""
        return f"{bungie}{suffix}"
    dn = player.get("displayName")
    if dn:
        return str(dn)
    mid = _norm_membership_id(player.get("membershipId"))
    return mid or "Unknown Player"


async def resolve_player_membership_id(raidhub: RaidHubClient, raw: str) -> str | None:
    info = await resolve_player_subscription_row(raidhub, raw)
    if not info:
        return None
    return _norm_membership_id(info.get("membershipId"))


async def resolve_player_subscription_row(
    raidhub: RaidHubClient, raw: str
) -> dict[str, Any] | None:
    """
    Resolve search text or digits to a RaidHub ``PlayerInfo``-shaped dict (for subscribe UX).
    """
    q = raw.strip()
    if not q:
        return None
    if re.fullmatch(r"\d+", q):
        mid = str(int(q))
        env = await raidhub.request_envelope("GET", f"/player/{mid}/basic")
        if env.get("success"):
            row = env.get("response")
            if isinstance(row, dict):
                return row
        return {"membershipId": mid}
    env = await raidhub.request_envelope(
        "GET",
        "/player/search",
        params={"query": q, "count": 1, "offset": 0},
    )
    if not env.get("success"):
        return None
    inner = env.get("response") or {}
    results = list(inner.get("results") or [])
    if not results:
        return None
    row = results[0]
    return row if isinstance(row, dict) else None
