from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..config import Settings
from ..log import handlers
from ..pagination import (
    build_triple_nav_action_row,
    parse_offset_page_nav_token,
    register_pager,
    store_paged_session,
)
from ..prom_metrics import observe_deferred_completion
from ..raidhub_client import RaidHubClient
from .shared import (
    USER_FACING_GENERIC,
    application_id,
    discord_message_for_failed_envelope,
    flatten_options,
    patch_discord_followup_best_effort,
)

PLAYER_SEARCH_PREFIX = "ps"
PLAYER_SEARCH_PAGE_SIZE = 10
_PLAYER_SEARCH_FIRST_PAGE_TOKEN = "0"


def _format_player_name(player: dict[str, Any]) -> str:
    bungie = player.get("bungieGlobalDisplayName")
    if bungie:
        code = player.get("bungieGlobalDisplayNameCode")
        suffix = f"#{code}" if code else ""
        return f"{bungie}{suffix}"
    return str(player.get("displayName") or "Unknown Player")


def _membership_id_str(player: dict[str, Any]) -> str:
    mid = player.get("membershipId")
    if mid is None:
        return ""
    return str(mid)


def _raidhub_profile_url(membership_id: str) -> str:
    return f"https://raidhub.io/profile/{membership_id}"


def _discord_relative_timestamp(iso_value: Any) -> str:
    if iso_value is None:
        return "—"
    s = str(iso_value).strip()
    if not s:
        return "—"
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ts = int(dt.timestamp())
    return f"<t:{ts}:R>"


def _embed_markdown_link_label(label: str) -> str:
    return label.replace("]", "")


def _format_player_search_line(rank: int, player: dict[str, Any]) -> str:
    name = _format_player_name(player)
    mid = _membership_id_str(player)
    seen = _discord_relative_timestamp(player.get("lastSeen"))
    if not mid:
        return f"**{rank}.** {name} · last seen {seen}"
    label = _embed_markdown_link_label(name)
    rh = _raidhub_profile_url(mid)
    return f"**{rank}.** [{label}]({rh}) · last seen {seen}"


async def _player_search_render_from_state(
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
    if "membershipType" in qp:
        params["membershipType"] = qp["membershipType"]
    if "global" in qp:
        params["global"] = qp["global"]

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
                    first_nav_token=_PLAYER_SEARCH_FIRST_PAGE_TOKEN,
                    prev_nav_token=f"p{page - 1}",
                    next_nav_token=f"n{page}",
                    first_disabled=False,
                    prev_disabled=False,
                    next_disabled=True,
                )
            ],
        }

    lines = [
        _format_player_search_line(offset + i + 1, player)
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
        first_nav_token=_PLAYER_SEARCH_FIRST_PAGE_TOKEN,
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
        return await _player_search_render_from_state(
            raidhub, st, session_id, nav_token
        )

    register_pager(
        PLAYER_SEARCH_PREFIX,
        _render,
        expired_message="This player search session expired. Run the command again.",
    )


async def run_player_search_deferred(
    interaction: dict[str, Any],
    raidhub: RaidHubClient,
    settings: Settings,
) -> None:
    app_id = application_id(interaction, settings)
    token = str(interaction.get("token") or "")
    outcome = "completed"
    try:
        opts = flatten_options(interaction.get("data", {}).get("options"))
        query = str(opts.get("search_query") or opts.get("query") or "").strip()
        if not query:
            await patch_discord_followup_best_effort(
                app_id, token, {"content": "Provide a **search_query** option to search."}
            )
            return

        query_params: dict[str, Any] = {"query": query}
        if "destiny_membership_type" in opts:
            query_params["membershipType"] = opts["destiny_membership_type"]
        elif "membership_type" in opts:
            query_params["membershipType"] = opts["membership_type"]
        if "use_global_name_search" in opts:
            query_params["global"] = opts["use_global_name_search"]
        elif "global" in opts:
            query_params["global"] = opts["global"]

        page_size = PLAYER_SEARCH_PAGE_SIZE
        session_id = store_paged_session(
            {"query_params": query_params, "page_size": page_size}
        )
        payload = await _player_search_render_from_state(
            raidhub,
            {"query_params": query_params, "page_size": page_size},
            session_id,
            "0",
        )
        await patch_discord_followup_best_effort(app_id, token, payload)
    except Exception as err:
        outcome = "error"
        handlers.error("PLAYER_SEARCH_DEFERRED_FAILED", err, {})
        await patch_discord_followup_best_effort(
            app_id, token, {"content": USER_FACING_GENERIC}
        )
    finally:
        observe_deferred_completion(command="player-search", outcome=outcome)


__all__ = ["register_player_search_pager", "run_player_search_deferred"]
