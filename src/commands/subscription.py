from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from ..config import Settings
from ..log import handlers
from ..prom_metrics import observe_deferred_completion
from ..raidhub_client import RaidHubClient, discord_invocation_context
from .shared import (
    USER_FACING_GENERIC,
    application_id,
    base_embed,
    discord_message_for_failed_envelope,
    error_embed,
    flatten_options,
    info_embed,
    patch_discord_followup_best_effort,
    success_embed,
    warn_embed,
)

# Must match RaidHub route ids for subscription Discord routes.
_SUB_ROUTE_PUT = "PUT subscriptions/discord/webhooks"
_SUB_ROUTE_DELETE = "DELETE subscriptions/discord/webhooks"
_SUB_ROUTE_STATUS = "GET subscriptions/discord/webhooks"


def _comma_separated_digit_ids(raw: str) -> list[str]:
    out: list[str] = []
    for part in raw.replace(",", " ").split():
        s = part.strip()
        if s and re.fullmatch(r"\d+", s):
            out.append(s)
    return out


def _subscription_json_body(leaf_opts: dict[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = {}
    wn = str(
        leaf_opts.get("discord_webhook_name")
        or leaf_opts.get("webhook_name")
        or ""
    ).strip()
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


def _format_subscription_status_embed(data: dict[str, Any]) -> dict[str, Any]:
    if not data.get("registered"):
        return info_embed(
            "Subscription Status",
            "No RaidHub subscription webhook is registered for this channel.",
        )
    active = "**yes**" if data.get("destinationActive") else "**no**"
    fails = int(data.get("consecutiveDeliveryFailures") or 0)
    fields: list[dict[str, Any]] = [
        {"name": "Destination Active", "value": active, "inline": True},
        {"name": "Webhook ID", "value": f"`{data.get('webhookId', '—')}`", "inline": True},
        {"name": "Delivery Failures", "value": f"**{fails}**", "inline": True},
    ]
    ls = data.get("lastDeliverySuccessAt")
    lf = data.get("lastDeliveryFailureAt")
    fields.append(
        {
            "name": "Last Delivery Success",
            "value": _discord_relative_timestamp(ls) if ls else "—",
            "inline": True,
        }
    )
    fields.append(
        {
            "name": "Last Delivery Failure",
            "value": _discord_relative_timestamp(lf) if lf else "—",
            "inline": True,
        }
    )
    err = data.get("lastDeliveryError")
    if err:
        fields.append({"name": "Last Error", "value": str(err)[:280], "inline": False})

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
    fields.append({"name": f"Player Rules ({pc})", "value": p_list[:1024], "inline": False})
    fields.append({"name": f"Clan Rules ({cc})", "value": c_list[:1024], "inline": False})
    return base_embed(
        title="Subscription Status",
        description="Current webhook destination and delivery health.",
        color=0x5865_F2,
        fields=fields,
    )


def subscription_envelope_error_message(env: dict[str, Any]) -> str:
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
    return discord_message_for_failed_envelope(code, "")


async def run_subscription_deferred(
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
                    "Subscription Command",
                    "Pick `register`, `update`, `delete`, or `status` under `/subscription`.",
                ),
            )
            return

        sub = str(top_opts[0].get("name") or "").strip().lower()
        if sub not in ("register", "update", "delete", "status"):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                warn_embed("Subscription Command", "Unknown `/subscription` subcommand."),
            )
            return

        if not interaction.get("guild_id") or not interaction.get("channel_id"):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                warn_embed(
                    "Subscription Command",
                    "Run this command in a server channel, not a DM.",
                ),
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
            await patch_discord_followup_best_effort(
                app_id,
                token,
                error_embed(
                    "Subscription Request Failed",
                    subscription_envelope_error_message(env),
                ),
            )
            return

        inner = env.get("response") or {}
        if sub == "status":
            msg = _format_subscription_status_embed(inner)
        elif sub == "delete":
            msg = success_embed(
                "Subscription Removed",
                "RaidHub will no longer use a webhook in this channel.",
            )
        elif sub == "register":
            parts = [
                "RaidHub subscription events will post to this channel.",
            ]
            if inner.get("created"):
                parts.append("A new subscription destination was created.")
            if inner.get("activated"):
                parts.append("The destination was re-activated.")
            rules = inner.get("rules") or {}
            rs = _subscription_rules_suffix(rules)
            if rs:
                parts.append(rs)
            msg = success_embed("Subscription Registered", " ".join(parts))
        else:
            parts = ["Subscription rules for this channel were saved."]
            if inner.get("activated"):
                parts.append("The destination was re-activated.")
            rules = inner.get("rules") or {}
            rs = _subscription_rules_suffix(rules)
            if rs:
                parts.append(rs)
            msg = success_embed("Subscription Updated", " ".join(parts))

        await patch_discord_followup_best_effort(app_id, token, msg)
    except Exception as err:
        outcome = "error"
        handlers.error("SUBSCRIPTION_DEFERRED_FAILED", err, {})
        await patch_discord_followup_best_effort(
            app_id, token, error_embed("Subscription Failed", USER_FACING_GENERIC)
        )
    finally:
        observe_deferred_completion(command="subscription", outcome=outcome)


__all__ = ["run_subscription_deferred", "subscription_envelope_error_message"]
