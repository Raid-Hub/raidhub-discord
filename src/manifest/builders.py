from __future__ import annotations

from .schema import CommandDto, CommandOptionDto, CommandOptionType


def subscription_filter_options() -> list[CommandOptionDto]:
    return [
        CommandOptionDto(
            type=CommandOptionType.BOOLEAN,
            name="require_fresh",
            description="Only notify for fresh (first-week) clears",
            required=False,
        ),
        CommandOptionDto(
            type=CommandOptionType.BOOLEAN,
            name="require_completed",
            description="Only notify when the activity completes",
            required=False,
        ),
        CommandOptionDto(
            type=CommandOptionType.STRING,
            name="players",
            description="Comma-separated Destiny membership IDs to filter to",
            required=False,
        ),
        CommandOptionDto(
            type=CommandOptionType.STRING,
            name="clans",
            description="Comma-separated Bungie clan group IDs to filter to",
            required=False,
        ),
    ]


def build_commands() -> list[CommandDto]:
    return [
        CommandDto(
            name="instance",
            description="Lookup a RaidHub instance by id.",
            options=[
                CommandOptionDto(
                    type=CommandOptionType.STRING,
                    name="raid_instance_id",
                    description="Instance id to lookup",
                    required=False,
                )
            ],
        ),
        CommandDto(
            name="player-search",
            description="Search RaidHub players by Bungie name or platform name.",
            options=[
                CommandOptionDto(
                    type=CommandOptionType.STRING,
                    name="search_query",
                    description="Search text",
                    required=True,
                ),
                CommandOptionDto(
                    type=CommandOptionType.INTEGER,
                    name="destiny_membership_type",
                    description="Destiny membership type",
                    required=False,
                ),
                CommandOptionDto(
                    type=CommandOptionType.BOOLEAN,
                    name="use_global_name_search",
                    description="Search by Bungie name",
                    required=False,
                ),
            ],
        ),
        CommandDto(
            name="subscribe",
            description="Subscribe this channel to a player or clan (resolves names & URLs here).",
            dm_permission=False,
            options=[
                CommandOptionDto(
                    type=CommandOptionType.SUB_COMMAND,
                    name="player",
                    description="Subscribe by membership id or player name (top search hit).",
                    options=[
                        CommandOptionDto(
                            type=CommandOptionType.STRING,
                            name="player_id_or_search_text",
                            description="Destiny membership id (digits) or player search text",
                            required=True,
                        )
                    ],
                ),
                CommandOptionDto(
                    type=CommandOptionType.SUB_COMMAND,
                    name="clan",
                    description="Subscribe by Bungie clan group id or clan page URL.",
                    options=[
                        CommandOptionDto(
                            type=CommandOptionType.STRING,
                            name="clan_group_id_or_url",
                            description="Numeric group id, raidhub.io/clan/…, or Bungie clan URL",
                            required=True,
                        )
                    ],
                ),
            ],
        ),
        CommandDto(
            name="subscription",
            description="Manage RaidHub subscription webhooks for this channel.",
            dm_permission=False,
            options=[
                CommandOptionDto(
                    type=CommandOptionType.SUB_COMMAND,
                    name="register",
                    description="Create a webhook here and register it with RaidHub.",
                    options=[
                        CommandOptionDto(
                            type=CommandOptionType.STRING,
                            name="discord_webhook_name",
                            description="Name shown in Discord for the incoming webhook",
                            required=False,
                        ),
                        *subscription_filter_options(),
                    ],
                ),
                CommandOptionDto(
                    type=CommandOptionType.SUB_COMMAND,
                    name="update",
                    description="Update filters or targets for this channel.",
                    options=subscription_filter_options(),
                ),
                CommandOptionDto(
                    type=CommandOptionType.SUB_COMMAND,
                    name="status",
                    description="Show whether this channel is registered and delivery health.",
                    options=[],
                ),
                CommandOptionDto(
                    type=CommandOptionType.SUB_COMMAND,
                    name="delete",
                    description="Remove the webhook destination and rules for this channel.",
                    options=[],
                ),
            ],
        ),
        CommandDto(
            name="unsubscribe",
            description="Remove the RaidHub subscription webhook from this channel.",
            dm_permission=False,
            options=[],
        ),
    ]
