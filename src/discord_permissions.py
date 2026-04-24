"""Discord permission helpers (keep free of httpx/jwt so tests can import cheaply)."""

from __future__ import annotations

from typing import Any

from .discord_v10_enums import Permission


def guild_member_has_manage_webhooks(interaction: dict[str, Any]) -> bool:
    """Whether the invoking guild member may configure channel webhooks (resolved permission bitfield)."""
    member = interaction.get("member")
    if not isinstance(member, dict):
        return False
    raw = member.get("permissions")
    if raw is None:
        return False
    try:
        perms = int(str(raw), 10)
    except (TypeError, ValueError):
        return False
    if perms & int(Permission.ADMINISTRATOR):
        return True
    return (perms & int(Permission.MANAGE_WEBHOOKS)) != 0
