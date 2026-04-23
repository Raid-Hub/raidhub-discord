from __future__ import annotations

import re
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


async def resolve_player_membership_id(raidhub: RaidHubClient, raw: str) -> str | None:
    q = raw.strip()
    if not q:
        return None
    if re.fullmatch(r"\d+", q):
        return q
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
    mid = results[0].get("membershipId")
    return str(mid) if mid is not None else None
