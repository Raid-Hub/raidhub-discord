from __future__ import annotations

import asyncio
import re
from typing import Any

from ..raidhub_client import RaidHubClient, discord_invocation_context
from .subscribe_resolution import format_player_display_name
from .subscription_routes import SUB_ROUTE_STATUS
from .shared import (
    base_embed,
    discord_message_for_failed_envelope,
    info_embed,
    iso_to_discord_relative,
)


def subscription_active_player_ids(inner: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for item in inner.get("players") or []:
        if isinstance(item, dict):
            raw = item.get("membershipId")
        else:
            raw = item
        if raw is None:
            continue
        s = str(raw).strip()
        if s.isdigit():
            out.append(str(int(s)))
    return sorted(set(out))


def subscription_active_clan_ids(inner: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for item in inner.get("clans") or []:
        if isinstance(item, dict):
            raw = item.get("groupId") or item.get("clanGroupId")
        else:
            raw = item
        if raw is None:
            continue
        s = str(raw).strip()
        if s.isdigit():
            out.append(str(int(s)))
    return sorted(set(out))


async def fetch_subscription_status_envelope(
    raidhub: RaidHubClient,
    interaction: dict[str, Any],
) -> dict[str, Any]:
    ctx = discord_invocation_context(interaction, route_id=SUB_ROUTE_STATUS)
    return await raidhub.request_envelope(
        "GET",
        "/subscriptions/discord/webhooks",
        discord_context=ctx,
    )


def build_subscription_json_body(leaf_opts: dict[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = {}
    wn = str(
        leaf_opts.get("discord_webhook_name") or leaf_opts.get("webhook_name") or ""
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


def _embed_safe_label(label: str) -> str:
    return label.replace("]", "")


def _raidhub_player_url(membership_id: str) -> str:
    return f"https://raidhub.io/profile/{membership_id}"


def _raidhub_clan_url(group_id: str) -> str:
    return f"https://raidhub.io/clan/{group_id}"


def format_clan_display_name(row: dict[str, Any]) -> str:
    name = str(row.get("name") or "").strip()
    tag = str(row.get("callSign") or "").strip()
    if name and tag:
        return f"{name} [{tag}]"
    return name or tag or "Unknown clan"


def _ordered_membership_ids(pl_raw: list[Any]) -> list[str]:
    out: list[str] = []
    for item in pl_raw:
        raw = item.get("membershipId") if isinstance(item, dict) else item
        if raw is None:
            continue
        s = str(raw).strip()
        if s.isdigit():
            norm = str(int(s))
            if norm not in out:
                out.append(norm)
    return out


def _ordered_group_ids(cl_raw: list[Any]) -> list[str]:
    out: list[str] = []
    for item in cl_raw:
        if isinstance(item, dict):
            raw = item.get("groupId") or item.get("clanGroupId")
        else:
            raw = item
        if raw is None:
            continue
        s = str(raw).strip()
        if s.isdigit():
            norm = str(int(s))
            if norm not in out:
                out.append(norm)
    return out


async def _fetch_player_basic_card(
    raidhub: RaidHubClient, membership_id: str
) -> dict[str, Any]:
    env = await raidhub.request_envelope("GET", f"/player/{membership_id}/basic")
    inner = env.get("response")
    return inner if env.get("success") and isinstance(inner, dict) else {}


async def _fetch_clan_basic_card(
    raidhub: RaidHubClient, group_id: str
) -> dict[str, Any]:
    env = await raidhub.request_envelope("GET", f"/clan/{group_id}/basic")
    inner = env.get("response")
    return inner if env.get("success") and isinstance(inner, dict) else {}


def _standardized_rule_string(rule: dict[str, Any]) -> str:
    fresh = "yes" if bool(rule.get("requireFresh")) else "no"
    completed = "yes" if bool(rule.get("requireCompleted")) else "no"
    raid_ids_raw = rule.get("raidIds")
    raid_ids: list[str] = []
    if isinstance(raid_ids_raw, list):
        for value in raid_ids_raw:
            s = str(value).strip()
            if s.isdigit():
                raid_ids.append(str(int(s)))

    # Backward compatibility for old API payloads.
    if not raid_ids:
        legacy_raid_id = rule.get("raidId")
        if legacy_raid_id is not None and str(legacy_raid_id).strip() != "":
            s = str(legacy_raid_id).strip()
            if s.isdigit():
                raid_ids = [str(int(s))]

    if raid_ids:
        raid = f"raids:{','.join(raid_ids)}"
    else:
        raid = "raids:all"
    return f"`fresh:{fresh}` `completed:{completed}` `{raid}`"


def _player_rule_line(
    membership_id: str, card: dict[str, Any], rule: dict[str, Any]
) -> str:
    rule_suffix = _standardized_rule_string(rule)
    if card:
        label = _embed_safe_label(format_player_display_name(card))
        url = _raidhub_player_url(membership_id)
        return f"• [{label}]({url}) · `{membership_id}` · {rule_suffix}"
    return f"• `{membership_id}` · {rule_suffix}"


def _clan_rule_line(group_id: str, card: dict[str, Any], rule: dict[str, Any]) -> str:
    rule_suffix = _standardized_rule_string(rule)
    if card:
        label = _embed_safe_label(format_clan_display_name(card))
        url = _raidhub_clan_url(group_id)
        return f"• [{label}]({url}) · `{group_id}` · {rule_suffix}"
    return f"• `{group_id}` · {rule_suffix}"


def _id_only_rule_lines(ids: list[str]) -> str:
    max_show = 25
    shown = ids[:max_show]
    lines = [f"• `{i}`" for i in shown]
    body = "\n".join(lines) if lines else "—"
    extra = len(ids) - len(shown)
    if extra > 0:
        body = f"{body}\n… and **{extra}** more (showing names requires API access)."
    return body[:1024]


def _indexed_player_rules(pl_raw: list[Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in pl_raw:
        if not isinstance(item, dict):
            continue
        raw = item.get("membershipId")
        if raw is None:
            continue
        s = str(raw).strip()
        if not s.isdigit():
            continue
        out[str(int(s))] = item
    return out


def _indexed_clan_rules(cl_raw: list[Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in cl_raw:
        if not isinstance(item, dict):
            continue
        raw = item.get("groupId") or item.get("clanGroupId")
        if raw is None:
            continue
        s = str(raw).strip()
        if not s.isdigit():
            continue
        out[str(int(s))] = item
    return out


def _rule_filter_state(items: list[Any], key: str) -> str:
    values = [item.get(key) for item in items if isinstance(item, dict) and key in item]
    bool_values = [bool(v) for v in values if isinstance(v, bool)]
    if not bool_values:
        return "unset"
    uniq = set(bool_values)
    if len(uniq) > 1:
        return "mixed"
    return "yes" if True in uniq else "no"


def _rule_filters_summary(pl_raw: list[Any], cl_raw: list[Any]) -> str:
    all_rules = [*pl_raw, *cl_raw]
    if not all_rules:
        return "—"
    fresh = _rule_filter_state(all_rules, "requireFresh")
    completed = _rule_filter_state(all_rules, "requireCompleted")
    return (f"Require Fresh: **{fresh}**\n" f"Require Completed: **{completed}**")[
        :1024
    ]


async def format_subscription_status_embed(
    raidhub: RaidHubClient | None,
    data: dict[str, Any],
) -> dict[str, Any]:
    if not data.get("registered"):
        return info_embed(
            "Subscription Status",
            "RaidHub alerts are currently turned off for this channel.",
        )
    active = "**yes**" if data.get("destinationActive") else "**no**"
    fails = int(data.get("consecutiveDeliveryFailures") or 0)
    fields: list[dict[str, Any]] = [
        {"name": "Destination Active", "value": active, "inline": True},
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
    pl_ids = _ordered_membership_ids(pl_raw)
    cl_ids = _ordered_group_ids(cl_raw)
    player_rules = _indexed_player_rules(pl_raw)
    clan_rules = _indexed_clan_rules(cl_raw)
    pc = len(pl_ids)
    cc = len(cl_ids)
    fields.append(
        {
            "name": "Rule Filters",
            "value": _rule_filters_summary(pl_raw, cl_raw),
            "inline": False,
        }
    )

    player_cards: dict[str, dict[str, Any]] = {}
    clan_cards: dict[str, dict[str, Any]] = {}
    if raidhub is not None and (pl_ids or cl_ids):
        p_res = (
            await asyncio.gather(
                *[_fetch_player_basic_card(raidhub, mid) for mid in pl_ids]
            )
            if pl_ids
            else []
        )
        c_res = (
            await asyncio.gather(
                *[_fetch_clan_basic_card(raidhub, gid) for gid in cl_ids]
            )
            if cl_ids
            else []
        )
        for mid, card in zip(pl_ids, p_res, strict=True):
            player_cards[mid] = card if isinstance(card, dict) else {}
        for gid, card in zip(cl_ids, c_res, strict=True):
            clan_cards[gid] = card if isinstance(card, dict) else {}

    if raidhub is None:
        p_lines = [
            f"• `{mid}` · {_standardized_rule_string(player_rules.get(mid, {}))}"
            for mid in pl_ids
        ]
        p_body = "\n".join(p_lines) if p_lines else "—"
        c_lines = [
            f"• `{gid}` · {_standardized_rule_string(clan_rules.get(gid, {}))}"
            for gid in cl_ids
        ]
        c_body = "\n".join(c_lines) if c_lines else "—"
        if len(p_body) > 1024:
            p_body = p_body[:1021] + "..."
        if len(c_body) > 1024:
            c_body = c_body[:1021] + "..."
    else:
        p_lines = [
            _player_rule_line(mid, player_cards.get(mid, {}), player_rules.get(mid, {}))
            for mid in pl_ids
        ]
        p_body = "\n".join(p_lines) if p_lines else "—"
        if len(p_body) > 1024:
            p_body = p_body[:1021] + "..."
        c_lines = [
            _clan_rule_line(gid, clan_cards.get(gid, {}), clan_rules.get(gid, {}))
            for gid in cl_ids
        ]
        c_body = "\n".join(c_lines) if c_lines else "—"
        if len(c_body) > 1024:
            c_body = c_body[:1021] + "..."

    fields.append({"name": f"Player Rules ({pc})", "value": p_body, "inline": False})
    fields.append({"name": f"Clan Rules ({cc})", "value": c_body, "inline": False})

    desc = "Current alert delivery health and active rules."
    if raidhub is not None and (pc + cc) > 1:
        desc = (
            f"{desc}\n\nShowing **{pc}** player(s) and **{cc}** clan(s) by name below "
            "(name and id view)."
        )

    return base_embed(
        title="Subscription Status",
        description=desc,
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
