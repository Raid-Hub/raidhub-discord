from __future__ import annotations

import re
from typing import Any

from .subscription_routes import SUB_ROUTE_DELETE, SUB_ROUTE_PUT, SUB_ROUTE_STATUS
from .shared import (
    base_embed,
    discord_message_for_failed_envelope,
    info_embed,
    iso_to_discord_relative,
)


def build_subscription_json_body(leaf_opts: dict[str, Any]) -> dict[str, Any]:
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


def subscription_rules_suffix(rules: dict[str, Any]) -> str:
    p = rules.get("players") or {}
    c = rules.get("clans") or {}
    pl = int(p.get("inserted", 0)) + int(p.get("updated", 0))
    cl = int(c.get("inserted", 0)) + int(c.get("updated", 0))
    if pl or cl:
        return f"Rule changes: {pl} player row(s), {cl} clan row(s)."
    return ""


def format_subscription_status_embed(data: dict[str, Any]) -> dict[str, Any]:
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
            "value": iso_to_discord_relative(ls) if ls else "—",
            "inline": True,
        }
    )
    fields.append(
        {
            "name": "Last Delivery Failure",
            "value": iso_to_discord_relative(lf) if lf else "—",
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


def _comma_separated_digit_ids(raw: str) -> list[str]:
    out: list[str] = []
    for part in raw.replace(",", " ").split():
        s = part.strip()
        if s and re.fullmatch(r"\d+", s):
            out.append(s)
    return out


