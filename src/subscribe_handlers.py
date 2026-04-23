"""
``/subscribe`` — resolve clan URLs / player names in-process, then call RaidHub
``PUT /subscriptions/discord/webhooks`` with numeric ids only.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from .config import Settings
from .interaction_handlers import (
    _application_id,
    _patch_discord_followup_best_effort,
    _subscription_envelope_error_message,
    USER_FACING_GENERIC,
    flatten_options,
)
from .log import handlers
from .prom_metrics import observe_deferred_completion
from .raidhub_client import RaidHubClient, discord_invocation_context

# Match RaidHub ``RaidHubRoute.getDerivedRouteId()`` for subscription routes.
_ROUTE_PUT = "PUT subscriptions/discord/webhooks"
_ROUTE_STATUS = "GET subscriptions/discord/webhooks"

_CLAN_GROUP_ID_PATTERNS = (
    re.compile(r"(?:https?://)?(?:www\.)?raidhub\.io/clan/(\d+)", re.I),
    re.compile(r"(?:https?://)?(?:www\.)?bungie\.net/[^?\s]*[?&]group(?:id|Id)=(\d+)", re.I),
    re.compile(r"/GroupV2/(\d+)", re.I),
    re.compile(r"/clan/(\d+)", re.I),
)


def parse_clan_group_id(raw: str) -> str | None:
    """
    Extract a Bungie **clan group id** from a bare id or common RaidHub / Bungie URLs.
    Heuristic path fallback: last path segment that is all digits (length ≥ 5).
    """
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
    """Digits-only → as-is; otherwise first ``GET /player/search`` hit (score order)."""
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
                {"content": "Use **`/subscribe player`** or **`/subscribe clan`** with a target."},
            )
            return

        sub = str(top_opts[0].get("name") or "").strip().lower()
        if sub not in ("player", "clan"):
            await _patch_discord_followup_best_effort(
                app_id, token, {"content": "Unknown `/subscribe` subcommand."}
            )
            return

        leaf = flatten_options(top_opts[0].get("options"))
        target_raw = str(leaf.get("target") or "").strip()
        if not target_raw:
            await _patch_discord_followup_best_effort(
                app_id,
                token,
                {"content": "Provide a **target** (membership id / player name, or clan id / URL)."},
            )
            return

        if not interaction.get("guild_id") or not interaction.get("channel_id"):
            await _patch_discord_followup_best_effort(
                app_id,
                token,
                {"content": "Run **`/subscribe`** in a **server text channel**, not a DM."},
            )
            return

        if sub == "player":
            mid = await resolve_player_membership_id(raidhub, target_raw)
            if not mid:
                await _patch_discord_followup_best_effort(
                    app_id,
                    token,
                    {
                        "content": (
                            "Could not resolve that player. Try a **Destiny membership id** "
                            "or a clearer **name** (first RaidHub search hit is used)."
                        )
                    },
                )
                return
            resolved_id = mid
            kind_label = "player"
            body: dict[str, Any] = {"targets": {"playerMembershipIds": [resolved_id]}}
        else:
            gid = parse_clan_group_id(target_raw)
            if not gid:
                await _patch_discord_followup_best_effort(
                    app_id,
                    token,
                    {
                        "content": (
                            "Could not parse a **clan group id** from that. Use digits only, "
                            "or a **raidhub.io/clan/…** / Bungie clan URL containing the group id."
                        )
                    },
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
            await _patch_discord_followup_best_effort(
                app_id,
                token,
                {"content": _subscription_envelope_error_message(env)},
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
        await _patch_discord_followup_best_effort(
            app_id,
            token,
            {
                "content": (
                    f"**Subscribed** ({action}) to **{kind_label}** `{resolved_id}` for this channel. "
                    "Use `/subscription status` to inspect delivery health and rules."
                )
            },
        )
    except Exception as e:
        outcome = "error"
        handlers.error("SUBSCRIBE_DEFERRED_FAILED", e, {})
        await _patch_discord_followup_best_effort(
            app_id,
            token,
            {"content": USER_FACING_GENERIC},
        )
    finally:
        observe_deferred_completion(command="subscribe", outcome=outcome)
