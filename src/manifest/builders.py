from __future__ import annotations

from .schema import CommandDto, CommandOptionChoiceDto, CommandOptionDto, CommandOptionType


def build_commands(raid_filter_choices: list[tuple[str, int]] | None = None) -> list[CommandDto]:
    raid_choices = [
        CommandOptionChoiceDto(name=name[:100], value=value)
        for name, value in (raid_filter_choices or [])
    ][:25]
    raid_option_choices = raid_choices or None
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
                        CommandOptionDto(
                            type=CommandOptionType.INTEGER,
                            name="raid",
                            description="Optional raid filter",
                            required=False,
                            choices=raid_option_choices,
                        ),
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
                        CommandOptionDto(
                            type=CommandOptionType.INTEGER,
                            name="raid",
                            description="Optional raid filter",
                            required=False,
                            choices=raid_option_choices,
                        ),
                    ],
                ),
            ],
        ),
        CommandDto(
            name="subscription",
            description="Inspect or remove the RaidHub subscription webhook for this channel.",
            dm_permission=False,
            options=[
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
            description="Remove player/clan rules or the webhook destination for this channel.",
            dm_permission=False,
            options=[
                CommandOptionDto(
                    type=CommandOptionType.SUB_COMMAND,
                    name="delete",
                    description="Remove the webhook destination and all rules for this channel.",
                    options=[],
                ),
                CommandOptionDto(
                    type=CommandOptionType.SUB_COMMAND,
                    name="player",
                    description="Remove one subscribed Destiny player from this channel.",
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
                    description="Remove one subscribed Bungie clan from this channel.",
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
