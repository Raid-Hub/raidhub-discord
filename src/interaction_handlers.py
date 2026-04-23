from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import httpx

from .config import Settings
from .log import handlers
from .prom_metrics import observe_deferred_completion
from .pagination import (
    build_triple_nav_action_row,
    parse_offset_page_nav_token,
    register_pager,
    store_paged_session,
)
from .raidhub_client import RaidHubClient, discord_invocation_context

PLAYER_SEARCH_PREFIX = "ps"
PLAYER_SEARCH_PAGE_SIZE = 10
# Nav token for first page (decoded by ``parse_offset_page_nav_token``).
_PLAYER_SEARCH_FIRST_PAGE_TOKEN = "0"

# Must match RaidHub ``RaidHubRoute.getDerivedRouteId()`` for subscription Discord routes.
_SUB_ROUTE_PUT = "PUT subscriptions/discord/webhooks"
_SUB_ROUTE_DELETE = "DELETE subscriptions/discord/webhooks"
_SUB_ROUTE_STATUS = "GET subscriptions/discord/webhooks"

# Never put raw HTTP exceptions, webhook URLs, or interaction tokens in these strings.
USER_FACING_GENERIC = "Something went wrong. Try the command again."
USER_FACING_DISCORD_UPDATE_FAILED = (
    "Could not update this message. Try the command again."
)


def _discord_message_for_failed_envelope(code: str, _detail: str) -> str:
    if code == "RaidHubApiUnreachable":
        return (
            "Could not connect to the RaidHub API. Set `RAIDHUB_API_BASE_URL` to a URL this "
            "host can reach from the network (for a cloud Discord app, `http://localhost:8000` "
            "is not reachable — use your public API base URL)."
        )
    if code == "RaidHubApiServerError":
        return (
            "RaidHub returned a server error (temporary outage or gateway timeout). "
            "Try again shortly."
        )
    if code == "RaidHubApiClientError":
        return "RaidHub could not process this request."
    if code == "NonJsonResponse":
        return "RaidHub returned an unexpected response."
    return USER_FACING_GENERIC


def flatten_options(options: list[dict[str, Any]] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if not options:
        return out
    for opt in options:
        if opt.get("options"):
            out.update(flatten_options(opt["options"]))
        if "value" in opt:
            out[opt["name"]] = opt["value"]
    return out


def _format_duration(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h}h {m}m {s}s"


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
    """Discord auto-updating relative time from an API ISO-8601 string (e.g. ``lastSeen``)."""
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
    """Strip ``]`` so ``[label](url)`` in embeds does not break on display names that contain ``]``."""
    return label.replace("]", "")


def _format_player_search_line(rank: int, player: dict[str, Any]) -> str:
    """One row: RaidHub profile link on the name, plus Discord-formatted last seen."""
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
    """
    Each page is a fresh ``GET /player/search`` with ``count=page_size`` and ``offset=page*page_size``.
    Session holds only query inputs, not result rows.
    """
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
            "content": _discord_message_for_failed_envelope(code, ""),
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
    body = "\n".join(lines)
    description = header + body
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


async def patch_discord_original(
    application_id: str, interaction_token: str, data: dict[str, Any]
) -> bool:
    """PATCH the deferred interaction message. Returns ``False`` on failure (never raises)."""
    url = f"https://discord.com/api/v10/webhooks/{application_id}/{interaction_token}/messages/@original"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.patch(url, json=data)
    except httpx.RequestError as e:
        handlers.warn(
            "DISCORD_PATCH_ORIGINAL_NETWORK",
            e,
            {"application_id": application_id},
        )
        return False
    if not r.is_success:
        handlers.warn(
            "DISCORD_PATCH_ORIGINAL_FAILED",
            None,
            {
                "application_id": application_id,
                "status_code": r.status_code,
                "body": r.text[:800],
            },
        )
        return False
    return True


async def _patch_discord_followup_best_effort(
    application_id: str, interaction_token: str, data: dict[str, Any]
) -> None:
    """Send primary payload; on failure send a generic line (never echo httpx URLs or tokens)."""
    if await patch_discord_original(application_id, interaction_token, data):
        return
    await patch_discord_original(
        application_id,
        interaction_token,
        {"content": USER_FACING_DISCORD_UPDATE_FAILED},
    )


def _application_id(interaction: dict[str, Any], settings: Settings) -> str:
    return str(
        interaction.get("application_id") or settings.discord_application_id or ""
    )


def _comma_separated_digit_ids(raw: str) -> list[str]:
    out: list[str] = []
    for part in raw.replace(",", " ").split():
        s = part.strip()
        if s and re.fullmatch(r"\d+", s):
            out.append(s)
    return out


def _subscription_json_body(leaf_opts: dict[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = {}
    wn = str(leaf_opts.get("webhook_name") or "").strip()
    if wn:
        body["name"] = wn[:80]
    filters: dict[str, Any] = {}
    if "require_fresh" in leaf_opts:
        filters["requireFresh"] = bool(leaf_opts["require_fresh"])
    if "require_completed" in leaf_opts:
        filters["requireCompleted"] = bool(leaf_opts["require_completed"])
    if filters:
        body["filters"] = filters
    targets: dict[str, Any] = {}
    players = _comma_separated_digit_ids(str(leaf_opts.get("players") or ""))
    if players:
        targets["playerMembershipIds"] = players
    clans = _comma_separated_digit_ids(str(leaf_opts.get("clans") or ""))
    if clans:
        targets["clanGroupIds"] = clans
    if targets:
        body["targets"] = targets
    return body


def _subscription_rules_suffix(rules: dict[str, Any]) -> str:
    p = rules.get("players") or {}
    c = rules.get("clans") or {}
    pl = int(p.get("inserted", 0)) + int(p.get("updated", 0))
    cl = int(c.get("inserted", 0)) + int(c.get("updated", 0))
    if pl or cl:
        return f"Rule changes: {pl} player row(s), {cl} clan row(s)."
    return ""


def _format_subscription_status_message(data: dict[str, Any]) -> str:
    if not data.get("registered"):
        return "No RaidHub subscription webhook is registered for **this channel**."
    active = "**yes**" if data.get("destinationActive") else "**no**"
    fails = int(data.get("consecutiveDeliveryFailures") or 0)
    lines = [
        "**Subscription status**",
        f"Destination active: {active}",
        f"Webhook ID: `{data.get('webhookId', '—')}`",
        f"Delivery failures (streak): **{fails}**",
    ]
    ls = data.get("lastDeliverySuccessAt")
    lf = data.get("lastDeliveryFailureAt")
    lines.append(
        f"Last delivery success: {_discord_relative_timestamp(ls) if ls else '—'}"
    )
    lines.append(
        f"Last delivery failure: {_discord_relative_timestamp(lf) if lf else '—'}"
    )
    err = data.get("lastDeliveryError")
    if err:
        lines.append(f"Last error: {str(err)[:280]}")

    pl_raw = list(data.get("players") or [])
    cl_raw = list(data.get("clans") or [])
    pl_ids = [
        str(item.get("membershipId") if isinstance(item, dict) else item)
        for item in pl_raw
        if item is not None
    ]
    cl_ids = [
        str(item.get("groupId") if isinstance(item, dict) else item)
        for item in cl_raw
        if item is not None
    ]
    pc = len(pl_ids)
    cc = len(cl_ids)
    max_show = 25
    p_show = pl_ids[:max_show]
    c_show = cl_ids[:max_show]
    p_list = ", ".join(p_show) if p_show else "—"
    if pc > len(p_show):
        p_list = f"{p_list} (+{pc - len(p_show)} more)"
    c_list = ", ".join(c_show) if c_show else "—"
    if cc > len(c_show):
        c_list = f"{c_list} (+{cc - len(c_show)} more)"
    lines.append(f"Player rules: **{pc}** ({p_list})")
    lines.append(f"Clan rules: **{cc}** ({c_list})")
    return "\n".join(lines)


def _subscription_envelope_error_message(env: dict[str, Any]) -> str:
    code = str(env.get("code", ""))
    if code == "InsufficientPermissionsError":
        return (
            "RaidHub rejected this request. Use a **server text channel** where the bot can "
            "**Manage Webhooks**, and ensure the API trusts your bot JWT."
        )
    if code == "BodyValidationError":
        return (
            "RaidHub could not validate the payload. Use digits only for **players** / **clans** "
            "lists (comma-separated)."
        )
    return _discord_message_for_failed_envelope(code, "")


async def run_subscription_deferred(
    interaction: dict[str, Any],
    raidhub: RaidHubClient,
    settings: Settings,
) -> None:
    app_id = _application_id(interaction, settings)
    token = str(interaction.get("token") or "")
    outcome = "completed"
    try:
        data = interaction.get("data") or {}
        top_opts = data.get("options") or []
        if not top_opts or not isinstance(top_opts[0], dict):
            await _patch_discord_followup_best_effort(
                app_id,
                token,
                {
                    "content": (
                        "Pick **register**, **update**, **delete**, or **status** under `/subscription`."
                    )
                },
            )
            return

        sub = str(top_opts[0].get("name") or "").strip().lower()
        if sub not in ("register", "update", "delete", "status"):
            await _patch_discord_followup_best_effort(
                app_id, token, {"content": "Unknown subscription subcommand."}
            )
            return

        if not interaction.get("guild_id") or not interaction.get("channel_id"):
            await _patch_discord_followup_best_effort(
                app_id,
                token,
                {"content": "Run this command in a **server channel**, not a DM."},
            )
            return

        leaf_opts = flatten_options(top_opts[0].get("options"))
        route_id = {
            "register": _SUB_ROUTE_PUT,
            "update": _SUB_ROUTE_PUT,
            "delete": _SUB_ROUTE_DELETE,
            "status": _SUB_ROUTE_STATUS,
        }[sub]
        ctx = discord_invocation_context(interaction, route_id=route_id)

        if sub == "status":
            env = await raidhub.request_envelope(
                "GET",
                "/subscriptions/discord/webhooks",
                discord_context=ctx,
            )
        elif sub == "delete":
            env = await raidhub.request_envelope(
                "DELETE",
                "/subscriptions/discord/webhooks",
                discord_context=ctx,
            )
        else:
            payload = _subscription_json_body(leaf_opts)
            env = await raidhub.request_envelope(
                "PUT",
                "/subscriptions/discord/webhooks",
                json=payload if payload else {},
                discord_context=ctx,
            )

        if not env.get("success"):
            await _patch_discord_followup_best_effort(
                app_id,
                token,
                {"content": _subscription_envelope_error_message(env)},
            )
            return

        inner = env.get("response") or {}
        if sub == "status":
            msg = _format_subscription_status_message(inner)
        elif sub == "delete":
            msg = "**Unregistered.** RaidHub will no longer use a webhook in this channel."
        elif sub == "register":
            parts = [
                "**Registered.** RaidHub subscription events will post to this channel.",
            ]
            if inner.get("created"):
                parts.append("A new subscription destination was created.")
            if inner.get("activated"):
                parts.append("The destination was re-activated.")
            rules = inner.get("rules") or {}
            rs = _subscription_rules_suffix(rules)
            if rs:
                parts.append(rs)
            msg = " ".join(parts)
        else:
            parts = ["**Updated.** Subscription rules for this channel were saved."]
            if inner.get("activated"):
                parts.append("The destination was re-activated.")
            rules = inner.get("rules") or {}
            rs = _subscription_rules_suffix(rules)
            if rs:
                parts.append(rs)
            msg = " ".join(parts)

        await _patch_discord_followup_best_effort(app_id, token, {"content": msg})
    except Exception as e:
        outcome = "error"
        handlers.error("SUBSCRIPTION_DEFERRED_FAILED", e, {})
        await _patch_discord_followup_best_effort(
            app_id, token, {"content": USER_FACING_GENERIC}
        )
    finally:
        observe_deferred_completion(command="subscription", outcome=outcome)


async def run_player_search_deferred(
    interaction: dict[str, Any],
    raidhub: RaidHubClient,
    settings: Settings,
) -> None:
    app_id = _application_id(interaction, settings)
    token = str(interaction.get("token") or "")
    outcome = "completed"
    try:
        opts = flatten_options(interaction.get("data", {}).get("options"))
        query = str(opts.get("query") or "").strip()
        if not query:
            await _patch_discord_followup_best_effort(
                app_id, token, {"content": "Provide a **query** option to search."}
            )
            return

        query_params: dict[str, Any] = {"query": query}
        if "membership_type" in opts:
            query_params["membershipType"] = opts["membership_type"]
        if "global" in opts:
            query_params["global"] = opts["global"]

        page_size = PLAYER_SEARCH_PAGE_SIZE
        session_id = store_paged_session(
            {"query_params": query_params, "page_size": page_size}
        )
        session_state: dict[str, Any] = {
            "query_params": query_params,
            "page_size": page_size,
        }
        payload = await _player_search_render_from_state(
            raidhub, session_state, session_id, "0"
        )
        await _patch_discord_followup_best_effort(app_id, token, payload)
    except Exception as e:
        outcome = "error"
        handlers.error("PLAYER_SEARCH_DEFERRED_FAILED", e, {})
        await _patch_discord_followup_best_effort(
            app_id, token, {"content": USER_FACING_GENERIC}
        )
    finally:
        observe_deferred_completion(command="player-search", outcome=outcome)


async def run_instance_deferred(
    interaction: dict[str, Any],
    raidhub: RaidHubClient,
    settings: Settings,
) -> None:
    app_id = _application_id(interaction, settings)
    token = str(interaction.get("token") or "")
    outcome = "completed"
    try:
        opts = flatten_options(interaction.get("data", {}).get("options"))
        raw_id = opts.get("instance_id")
        if raw_id is None or str(raw_id).strip() == "":
            await _patch_discord_followup_best_effort(
                app_id, token, {"content": "Provide an **instance_id** to look up."}
            )
            return
        instance_id = str(raw_id).strip()

        env = await raidhub.request_envelope("GET", f"/instance/{instance_id}")
        if not env.get("success"):
            code = str(env.get("code", ""))
            if code == "InstanceNotFoundError":
                await _patch_discord_followup_best_effort(
                    app_id, token, {"content": "Instance not found."}
                )
                return
            await _patch_discord_followup_best_effort(
                app_id,
                token,
                {"content": _discord_message_for_failed_envelope(code, "")},
            )
            return

        inst = env.get("response") or {}
        meta = inst.get("metadata") or {}
        title = str(meta.get("activityName") or "Raid instance")
        desc = f"Instance `{inst.get('instanceId', instance_id)}`"
        date_done = inst.get("dateCompleted")
        date_s = str(date_done) if date_done else "—"
        embed = {
            "title": title,
            "description": desc,
            "color": 0x5865_F2,
            "fields": [
                {
                    "name": "Version",
                    "value": str(meta.get("versionName") or "—"),
                    "inline": True,
                },
                {
                    "name": "Players",
                    "value": str(inst.get("playerCount", "—")),
                    "inline": True,
                },
                {
                    "name": "Duration",
                    "value": _format_duration(int(inst.get("duration") or 0)),
                    "inline": True,
                },
                {
                    "name": "Completed",
                    "value": "Yes" if inst.get("completed") else "No",
                    "inline": True,
                },
                {
                    "name": "Fresh",
                    "value": "Yes" if inst.get("fresh") else "No",
                    "inline": True,
                },
                {
                    "name": "Flawless",
                    "value": "Yes" if inst.get("flawless") else "No",
                    "inline": True,
                },
                {"name": "Completed At", "value": date_s, "inline": False},
            ],
        }
        await _patch_discord_followup_best_effort(app_id, token, {"embeds": [embed]})
    except Exception as e:
        outcome = "error"
        handlers.error("INSTANCE_DEFERRED_FAILED", e, {})
        await _patch_discord_followup_best_effort(
            app_id, token, {"content": USER_FACING_GENERIC}
        )
    finally:
        observe_deferred_completion(command="instance", outcome=outcome)
