from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from ..config import Settings
from ..log import handlers
from ..raidhub_client import RaidHubEnvelopeCode

# Never put raw HTTP exceptions, webhook URLs, or interaction tokens in these strings.
USER_FACING_GENERIC = "Something went wrong. Try the command again."
USER_FACING_DISCORD_UPDATE_FAILED = (
    "Could not update this message. Try the command again."
)


def base_embed(
    *,
    title: str,
    description: str,
    color: int,
    fields: list[dict[str, Any]] | None = None,
    thumbnail_url: str | None = None,
    author_name: str | None = None,
    author_icon_url: str | None = None,
) -> dict[str, Any]:
    embed: dict[str, Any] = {
        "title": title,
        "description": description[:4096],
        "color": color,
    }
    if author_name or author_icon_url:
        author: dict[str, Any] = {}
        if author_name:
            author["name"] = author_name[:256]
        if author_icon_url:
            author["icon_url"] = author_icon_url[:2048]
        embed["author"] = author
    if thumbnail_url:
        embed["thumbnail"] = {"url": thumbnail_url[:2048]}
    if fields:
        embed["fields"] = fields[:25]
    return {"embeds": [embed], "components": []}


def info_embed(title: str, description: str) -> dict[str, Any]:
    return base_embed(title=title, description=description, color=0x5865_F2)


def success_embed(
    title: str,
    description: str,
    *,
    thumbnail_url: str | None = None,
    author_name: str | None = None,
    author_icon_url: str | None = None,
) -> dict[str, Any]:
    return base_embed(
        title=title,
        description=description,
        color=0x57_F287,
        thumbnail_url=thumbnail_url,
        author_name=author_name,
        author_icon_url=author_icon_url,
    )


def warn_embed(title: str, description: str) -> dict[str, Any]:
    return base_embed(title=title, description=description, color=0xFEE7_5C)


def error_embed(title: str, description: str) -> dict[str, Any]:
    return base_embed(title=title, description=description, color=0xED42_45)


def discord_message_for_failed_envelope(code: str, _detail: str) -> str:
    if code == RaidHubEnvelopeCode.RAIDHUB_API_UNREACHABLE.value:
        return (
            "Could not connect to the RaidHub API. Set `RAIDHUB_API_BASE_URL` to a URL this "
            "host can reach from the network (for a cloud Discord app, `http://localhost:8000` "
            "is not reachable - use your public API base URL)."
        )
    if code == RaidHubEnvelopeCode.RAIDHUB_API_SERVER_ERROR.value:
        return (
            "RaidHub returned a server error (temporary outage or gateway timeout). "
            "Try again shortly."
        )
    if code == RaidHubEnvelopeCode.RAIDHUB_API_CLIENT_ERROR.value:
        return "RaidHub could not process this request."
    if code == RaidHubEnvelopeCode.NON_JSON_RESPONSE.value:
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


def iso_to_discord_relative(iso_value: Any) -> str:
    if iso_value is None:
        return "—"
    s = str(iso_value).strip()
    if not s:
        return "—"
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ts = int(dt.timestamp())
    return f"<t:{ts}:R>"


def application_id(interaction: dict[str, Any], settings: Settings) -> str:
    return str(
        interaction.get("application_id") or settings.discord_application_id or ""
    )


async def patch_discord_original(
    discord_application_id: str, interaction_token: str, data: dict[str, Any]
) -> bool:
    """PATCH the deferred interaction message. Returns False on failure (never raises)."""
    url = f"https://discord.com/api/v10/webhooks/{discord_application_id}/{interaction_token}/messages/@original"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.patch(url, json=data)
    except httpx.RequestError as err:
        handlers.warn(
            "DISCORD_PATCH_ORIGINAL_NETWORK",
            err,
            {"application_id": discord_application_id},
        )
        return False
    if not response.is_success:
        handlers.warn(
            "DISCORD_PATCH_ORIGINAL_FAILED",
            None,
            {
                "application_id": discord_application_id,
                "status_code": response.status_code,
                "body": response.text[:800],
            },
        )
        return False
    return True


async def patch_discord_followup_best_effort(
    discord_application_id: str, interaction_token: str, data: dict[str, Any]
) -> None:
    """Send primary payload; on failure send a generic line."""
    if await patch_discord_original(discord_application_id, interaction_token, data):
        return
    await patch_discord_original(
        discord_application_id,
        interaction_token,
        {"content": USER_FACING_DISCORD_UPDATE_FAILED},
    )


async def report_deferred_exception(
    *,
    command: str,
    log_key: str,
    err: Exception,
    discord_application_id: str,
    interaction_token: str,
    user_message_payload: dict[str, Any],
) -> None:
    handlers.error(
        log_key,
        err,
        {
            "command": command,
            "component": "discord_deferred_handler",
            "application_id": discord_application_id,
            "has_interaction_token": bool(interaction_token),
        },
    )
    await patch_discord_followup_best_effort(
        discord_application_id, interaction_token, user_message_payload
    )
