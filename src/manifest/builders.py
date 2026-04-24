from __future__ import annotations

from ..discord_v10_enums import Permission
from .schema import CommandDto, CommandOptionDto, CommandOptionType

# Slash commands that configure RaidHub webhooks for a channel require the same baseline
# Discord permission as managing native webhooks in that channel.
_DEFAULT_MANAGE_WEBHOOKS = str(int(Permission.MANAGE_WEBHOOKS))


def build_commands(
    raid_filter_choices: list[tuple[str, int]] | None = None,
) -> list[CommandDto]:
    return [
        CommandDto(
            name="search",
            description="Search RaidHub players by Bungie name or platform name.",
            options=[
                CommandOptionDto(
                    type=CommandOptionType.STRING,
                    name="search_query",
                    description="Search text",
                    required=True,
                ),
            ],
        ),
        CommandDto(
            name="subscribe",
            description="Subscribe this channel to a player or clan (resolves names & URLs here).",
            dm_permission=False,
            default_member_permissions=_DEFAULT_MANAGE_WEBHOOKS,
            options=[
                CommandOptionDto(
                    type=CommandOptionType.SUB_COMMAND,
                    name="player",
                    description="Subscribe by membership id or player name (top search hit).",
                    options=[
                        CommandOptionDto(
                            type=CommandOptionType.STRING,
                            name="player",
                            description="Destiny membership id (digits) or player name",
                            required=True,
                        ),
                        CommandOptionDto(
                            type=CommandOptionType.BOOLEAN,
                            name="require_fresh",
                            description="Only send fresh completions",
                            required=False,
                        ),
                        CommandOptionDto(
                            type=CommandOptionType.BOOLEAN,
                            name="require_completed",
                            description="Only send completed runs",
                            required=False,
                        ),
                        # TODO: Reintroduce raid filtering after finalizing a user-friendly
                        # multi-select UX for Discord slash commands.
                    ],
                ),
                CommandOptionDto(
                    type=CommandOptionType.SUB_COMMAND,
                    name="clan",
                    description="Subscribe by Bungie clan group id or clan page URL.",
                    options=[
                        CommandOptionDto(
                            type=CommandOptionType.STRING,
                            name="clan",
                            description="Numeric group id, raidhub.io/clan/…, or Bungie clan URL",
                            required=True,
                        ),
                        CommandOptionDto(
                            type=CommandOptionType.BOOLEAN,
                            name="require_fresh",
                            description="Only send fresh completions",
                            required=False,
                        ),
                        CommandOptionDto(
                            type=CommandOptionType.BOOLEAN,
                            name="require_completed",
                            description="Only send completed runs",
                            required=False,
                        ),
                        # TODO: Reintroduce raid filtering after finalizing a user-friendly
                        # multi-select UX for Discord slash commands.
                    ],
                ),
            ],
        ),
        CommandDto(
            name="subscriptions",
            description="View this channel's RaidHub subscription status and rule health.",
            dm_permission=False,
            default_member_permissions=_DEFAULT_MANAGE_WEBHOOKS,
            options=[],
        ),
        CommandDto(
            name="unsubscribe",
            description="Turn off all RaidHub alerts for this channel.",
            dm_permission=False,
            default_member_permissions=_DEFAULT_MANAGE_WEBHOOKS,
            options=[
                CommandOptionDto(
                    type=CommandOptionType.SUB_COMMAND,
                    name="all",
                    description="Turn off all RaidHub alerts for this channel.",
                    options=[],
                ),
                CommandOptionDto(
                    type=CommandOptionType.SUB_COMMAND,
                    name="player",
                    description="Remove one subscribed player from this channel.",
                    options=[
                        CommandOptionDto(
                            type=CommandOptionType.STRING,
                            name="player",
                            description="Destiny membership id (digits) or player name",
                            required=True,
                        )
                    ],
                ),
                CommandOptionDto(
                    type=CommandOptionType.SUB_COMMAND,
                    name="clan",
                    description="Remove one subscribed clan from this channel.",
                    options=[
                        CommandOptionDto(
                            type=CommandOptionType.STRING,
                            name="clan",
                            description="Numeric group id, raidhub.io/clan/…, or Bungie clan URL",
                            required=True,
                        )
                    ],
                ),
            ],
        ),
    ]
