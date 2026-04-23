"""
`/subscribe` command: resolve clan URLs / player names, then register webhook targets.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from ..config import Settings
from ..log import handlers
from ..prom_metrics import observe_deferred_completion
from ..raidhub_client import RaidHubClient, discord_invocation_context
from .shared import (
    USER_FACING_GENERIC,
    application_id,
    error_embed,
    flatten_options,
    patch_discord_followup_best_effort,
    success_embed,
    warn_embed,
)
from .subscription import subscription_envelope_error_message

_ROUTE_PUT = "PUT subscriptions/discord/webhooks"

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


async def run_subscribe_deferred(
    interaction: dict[str, Any],
    raidhub: RaidHubClient,
    settings: Settings,
) -> None:
    app_id = application_id(interaction, settings)
    token = str(interaction.get("token") or "")
    outcome = "completed"
    try:
        data = interaction.get("data") or {}
        top_opts = data.get("options") or []
        if not top_opts or not isinstance(top_opts[0], dict):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                warn_embed(
                    "Subscribe Command",
                    "Use `/subscribe player` or `/subscribe clan` with a target.",
                ),
            )
            return

        sub = str(top_opts[0].get("name") or "").strip().lower()
        if sub not in ("player", "clan"):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                warn_embed("Subscribe Command", "Unknown `/subscribe` subcommand."),
            )
            return

        leaf = flatten_options(top_opts[0].get("options"))
        target_raw = str(
            leaf.get("player_id_or_search_text")
            or leaf.get("clan_group_id_or_url")
            or leaf.get("target")
            or ""
        ).strip()
        if not target_raw:
            await patch_discord_followup_best_effort(
                app_id,
                token,
                warn_embed(
                    "Subscribe Command",
                    "Provide a target (membership id / player name, or clan id / URL).",
                ),
            )
            return

        if not interaction.get("guild_id") or not interaction.get("channel_id"):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                warn_embed(
                    "Subscribe Command",
                    "Run `/subscribe` in a server text channel, not a DM.",
                ),
            )
            return

        if sub == "player":
            mid = await resolve_player_membership_id(raidhub, target_raw)
            if not mid:
                await patch_discord_followup_best_effort(
                    app_id,
                    token,
                    error_embed(
                        "Player Not Found",
                        "Could not resolve that player. Try a Destiny membership id or a clearer"
                        " name (first RaidHub search hit is used).",
                    ),
                )
                return
            resolved_id = mid
            kind_label = "player"
            body: dict[str, Any] = {"targets": {"playerMembershipIds": [resolved_id]}}
        else:
            gid = parse_clan_group_id(target_raw)
            if not gid:
                await patch_discord_followup_best_effort(
                    app_id,
                    token,
                    error_embed(
                        "Clan ID Not Recognized",
                        "Could not parse a clan group id from that value. Use digits only, or a"
                        " raidhub.io/clan/... / Bungie clan URL containing the group id.",
                    ),
                )
                return
            resolved_id = gid
            kind_label = "clan"
            body = {"targets": {"clanGroupIds": [resolved_id]}}

        ctx = discord_invocation_context(interaction, route_id=_ROUTE_PUT)
        env = await raidhub.request_envelope(
            "PUT",
            "/subscriptions/discord/webhooks",
            json=body,
            discord_context=ctx,
        )

        if not env.get("success"):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                error_embed(
                    "Subscribe Failed",
                    subscription_envelope_error_message(env),
                ),
            )
            return

        inner_put = env.get("response") or {}
        action = (
            "updated"
            if inner_put.get("updated")
            else "registered"
            if inner_put.get("created") or inner_put.get("webhookUrl")
            else "saved"
        )
        await patch_discord_followup_best_effort(
            app_id,
            token,
            success_embed(
                "Subscription Saved",
                f"Subscribed ({action}) to {kind_label} `{resolved_id}` for this channel. "
                "Use `/subscription status` to inspect delivery health and rules.",
            ),
        )
    except Exception as err:
        outcome = "error"
        handlers.error("SUBSCRIBE_DEFERRED_FAILED", err, {})
        await patch_discord_followup_best_effort(
            app_id,
            token,
            error_embed("Subscribe Failed", USER_FACING_GENERIC),
        )
    finally:
        observe_deferred_completion(command="subscribe", outcome=outcome)


__all__ = ["run_subscribe_deferred", "resolve_player_membership_id", "parse_clan_group_id"]
