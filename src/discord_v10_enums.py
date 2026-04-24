"""Numeric enums for Discord API v10 (no official all-in-one Python package; mirrors API docs)."""

from __future__ import annotations

from enum import IntEnum


class ApplicationCommandType(IntEnum):
    """https://discord.com/developers/docs/interactions/application-commands#applicationcommandobject"""

    CHAT_INPUT = 1
    USER = 2
    MESSAGE = 3


class ApplicationCommandOptionType(IntEnum):
    """https://discord.com/developers/docs/interactions/application-commands#applicationcommandoptionobject"""

    SUB_COMMAND = 1
    SUB_COMMAND_GROUP = 2
    STRING = 3
    INTEGER = 4
    BOOLEAN = 5
    USER = 6
    CHANNEL = 7
    ROLE = 8
    MENTIONABLE = 9
    NUMBER = 10
    ATTACHMENT = 11


class ComponentType(IntEnum):
    """https://discord.com/developers/docs/components/reference#component-object-component-types"""

    ACTION_ROW = 1
    BUTTON = 2
    STRING_SELECT = 3
    TEXT_INPUT = 4
    USER_SELECT = 5
    ROLE_SELECT = 6
    MENTIONABLE_SELECT = 7
    CHANNEL_SELECT = 8
    SECTION = 9
    TEXT_DISPLAY = 10
    THUMBNAIL = 11
    MEDIA_GALLERY = 12
    FILE = 13
    SEPARATOR = 14
    CONTAINER = 17
    LABEL = 18


class ButtonStyle(IntEnum):
    """https://discord.com/developers/docs/components/reference#button-object-button-styles"""

    PRIMARY = 1
    SECONDARY = 2
    SUCCESS = 3
    DANGER = 4
    LINK = 5


class Permission(IntEnum):
    """https://discord.com/developers/docs/topics/permissions#permissions-bitwise"""

    ADMINISTRATOR = 1 << 3
    MANAGE_WEBHOOKS = 1 << 29
