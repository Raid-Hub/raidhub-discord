from __future__ import annotations

from typing import Any

from .discord_v10_enums import ApplicationCommandOptionType, ApplicationCommandType


def _subscription_filter_options() -> list[dict[str, Any]]:
    return [
        {
            "type": int(ApplicationCommandOptionType.BOOLEAN),
            "name": "require_fresh",
            "description": "Only notify for fresh (first-week) clears",
            "required": False,
        },
        {
            "type": int(ApplicationCommandOptionType.BOOLEAN),
            "name": "require_completed",
            "description": "Only notify when the activity completes",
            "required": False,
        },
        {
            "type": int(ApplicationCommandOptionType.STRING),
            "name": "players",
            "description": "Comma-separated Destiny membership IDs to filter to",
            "required": False,
        },
        {
            "type": int(ApplicationCommandOptionType.STRING),
            "name": "clans",
            "description": "Comma-separated Bungie clan group IDs to filter to",
            "required": False,
        },
    ]


def build_command_manifest() -> list[dict[str, Any]]:
    sc = int(ApplicationCommandOptionType.SUB_COMMAND)
    return [
        {
            "name": "instance",
            "description": "Lookup a RaidHub instance by id.",
            "type": int(ApplicationCommandType.CHAT_INPUT),
            "options": [
                {
                    "type": int(ApplicationCommandOptionType.STRING),
                    "name": "instance_id",
                    "description": "Instance id to lookup",
                    "required": False,
                }
            ],
        },
        {
            "name": "player-search",
            "description": "Search RaidHub players by Bungie name or platform name.",
            "type": int(ApplicationCommandType.CHAT_INPUT),
            "options": [
                {
                    "type": int(ApplicationCommandOptionType.STRING),
                    "name": "query",
                    "description": "Search text",
                    "required": False,
                },
                {
                    "type": int(ApplicationCommandOptionType.INTEGER),
                    "name": "count",
                    "description": "Max results to return",
                    "required": False,
                },
                {
                    "type": int(ApplicationCommandOptionType.INTEGER),
                    "name": "membership_type",
                    "description": "Destiny membership type",
                    "required": False,
                },
                {
                    "type": int(ApplicationCommandOptionType.BOOLEAN),
                    "name": "global",
                    "description": "Search by Bungie name",
                    "required": False,
                },
            ],
        },
        {
            "name": "subscribe",
            "description": "Subscribe this channel to a player or clan (resolves names & URLs here).",
            "type": int(ApplicationCommandType.CHAT_INPUT),
            "options": [
                {
                    "type": sc,
                    "name": "player",
                    "description": "Subscribe by membership id or player name (top search hit).",
                    "options": [
                        {
                            "type": int(ApplicationCommandOptionType.STRING),
                            "name": "target",
                            "description": "Destiny membership id (digits) or player search text",
                            "required": True,
                        }
                    ],
                },
                {
                    "type": sc,
                    "name": "clan",
                    "description": "Subscribe by Bungie clan group id or clan page URL.",
                    "options": [
                        {
                            "type": int(ApplicationCommandOptionType.STRING),
                            "name": "target",
                            "description": "Numeric group id, raidhub.io/clan/…, or Bungie clan URL",
                            "required": True,
                        }
                    ],
                },
            ],
        },
        {
            "name": "subscription",
            "description": "Manage RaidHub subscription webhooks for this channel.",
            "type": int(ApplicationCommandType.CHAT_INPUT),
            "options": [
                {
                    "type": sc,
                    "name": "register",
                    "description": "Create a webhook here and register it with RaidHub.",
                    "options": [
                        {
                            "type": int(ApplicationCommandOptionType.STRING),
                            "name": "webhook_name",
                            "description": "Name shown in Discord for the incoming webhook",
                            "required": False,
                        },
                        *_subscription_filter_options(),
                    ],
                },
                {
                    "type": sc,
                    "name": "update",
                    "description": "Update filters or targets for this channel.",
                    "options": _subscription_filter_options(),
                },
                {
                    "type": sc,
                    "name": "status",
                    "description": "Show whether this channel is registered and delivery health.",
                    "options": [],
                },
            ],
        },
        {
            "name": "unsubscribe",
            "description": "Remove the RaidHub subscription webhook from this channel.",
            "type": int(ApplicationCommandType.CHAT_INPUT),
            "options": [],
        },
    ]
