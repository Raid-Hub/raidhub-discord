from __future__ import annotations

from typing import Any

from ..pagination import (
    build_triple_nav_action_row,
    parse_offset_page_nav_token,
    register_pager,
)
from ..raidhub_client import RaidHubClient
from .shared import (
    USER_FACING_GENERIC,
    discord_message_for_failed_envelope,
    iso_to_discord_relative,
)

PLAYER_SEARCH_PREFIX = "ps"
PLAYER_SEARCH_PAGE_SIZE = 10
PLAYER_SEARCH_FIRST_PAGE_TOKEN = "0"


def format_player_name(player: dict[str, Any]) -> str:
    bungie = player.get("bungieGlobalDisplayName")
    if bungie:
        code = player.get("bungieGlobalDisplayNameCode")
        suffix = f"#{code}" if code else ""
        return f"{bungie}{suffix}"
    return str(player.get("displayName") or "Unknown Player")


def membership_id_str(player: dict[str, Any]) -> str:
    mid = player.get("membershipId")
    if mid is None:
        return ""
    return str(mid)


def raidhub_profile_url(membership_id: str) -> str:
    return f"https://raidhub.io/profile/{membership_id}"


def embed_markdown_link_label(label: str) -> str:
    return label.replace("]", "")


def format_player_search_line(rank: int, player: dict[str, Any]) -> str:
    name = format_player_name(player)
    mid = membership_id_str(player)
    seen = iso_to_discord_relative(player.get("lastSeen"))
    if not mid:
        return f"**{rank}.** {name} · last seen {seen}"
    label = embed_markdown_link_label(name)
    rh = raidhub_profile_url(mid)
    return f"**{rank}.** [{label}]({rh}) · last seen {seen}"


async def player_search_render_from_state(
    raidhub: RaidHubClient,
    state: dict[str, Any],
    session_id: str,
    nav_token: str,
) -> dict[str, Any]:
    page = parse_offset_page_nav_token(nav_token, default=0)
    if page < 0:
        page = 0

    qp = dict(state.get("query_params") or {})
    query = str(qp.get("query") or "").strip()
    if not query:
        return {"content": USER_FACING_GENERIC}

    page_size = int(state.get("page_size") or PLAYER_SEARCH_PAGE_SIZE)
    offset = page * page_size

    params: dict[str, Any] = {"query": query, "count": page_size, "offset": offset}

    env = await raidhub.request_envelope("GET", "/player/search", params=params)
    if not env.get("success"):
        code = str(env.get("code", "Error"))
        return {
            "content": discord_message_for_failed_envelope(code, ""),
            "components": [],
        }

    inner = env.get("response") or {}
    results = list(inner.get("results") or [])
    q_label = str((inner.get("params") or {}).get("query", query))
    has_more = len(results) == page_size

    if not results:
        if page == 0:
            return {"content": f"No players found for `{q_label}`."}
        return {
            "content": (
                f"No more results on this page for `{q_label}`. "
                "Use **Start** to return to the first page or **Prev**."
            ),
            "components": [
                build_triple_nav_action_row(
                    prefix=PLAYER_SEARCH_PREFIX,
                    session_id=session_id,
                    first_nav_token=PLAYER_SEARCH_FIRST_PAGE_TOKEN,
                    prev_nav_token=f"p{page - 1}",
                    next_nav_token=f"n{page}",
                    first_disabled=False,
                    prev_disabled=False,
                    next_disabled=True,
                )
            ],
        }

    lines = [
        format_player_search_line(offset + i + 1, player)
        for i, player in enumerate(results)
    ]
    range_hi = offset + len(results)
    header = (
        f"Query: `{q_label}`\nPage **{page + 1}** — **{offset + 1}–{range_hi}** "
        f"({len(results)} on this page).\n\n"
    )
    description = header + "\n".join(lines)
    if len(description) > 4096:
        description = description[:4093] + "..."

    embed = {
        "title": "Player Search Results",
        "description": description,
        "color": 0x57_F287,
    }
    pager = build_triple_nav_action_row(
        prefix=PLAYER_SEARCH_PREFIX,
        session_id=session_id,
        first_nav_token=PLAYER_SEARCH_FIRST_PAGE_TOKEN,
        prev_nav_token=f"p{page - 1}",
        next_nav_token=f"n{page + 1}",
        first_disabled=page <= 0,
        prev_disabled=page <= 0,
        next_disabled=not has_more,
    )
    return {"embeds": [embed], "components": [pager]}


def register_player_search_pager(raidhub: RaidHubClient) -> None:
    async def _render(
        st: dict[str, Any], session_id: str, nav_token: str
    ) -> dict[str, Any]:
        return await player_search_render_from_state(raidhub, st, session_id, nav_token)

    register_pager(
        PLAYER_SEARCH_PREFIX,
        _render,
        expired_message="This player search session expired. Run the command again.",
    )
