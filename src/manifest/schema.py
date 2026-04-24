from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from ..discord_v10_enums import ApplicationCommandOptionType, ApplicationCommandType


class CommandType(IntEnum):
    CHAT_INPUT = int(ApplicationCommandType.CHAT_INPUT)


class CommandOptionType(IntEnum):
    SUB_COMMAND = int(ApplicationCommandOptionType.SUB_COMMAND)
    STRING = int(ApplicationCommandOptionType.STRING)
    INTEGER = int(ApplicationCommandOptionType.INTEGER)
    BOOLEAN = int(ApplicationCommandOptionType.BOOLEAN)


@dataclass(frozen=True, slots=True)
class CommandOptionChoiceDto:
    name: str
    value: str | int

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
        }


@dataclass(frozen=True, slots=True)
class CommandOptionDto:
    type: CommandOptionType
    name: str
    description: str
    required: bool | None = None
    options: list["CommandOptionDto"] | None = None
    choices: list[CommandOptionChoiceDto] | None = None

    def to_json(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "type": int(self.type),
            "name": self.name,
            "description": self.description,
        }
        if self.required is not None:
            data["required"] = self.required
        if self.choices is not None:
            data["choices"] = [c.to_json() for c in self.choices]
        if self.options is not None:
            data["options"] = [o.to_json() for o in self.options]
        return data


@dataclass(frozen=True, slots=True)
class CommandDto:
    name: str
    description: str
    type: CommandType = CommandType.CHAT_INPUT
    dm_permission: bool | None = None
    # Discord default_member_permissions bitfield as a decimal string (e.g. Manage Webhooks).
    default_member_permissions: str | None = None
    options: list[CommandOptionDto] | None = None

    def to_json(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "type": int(self.type),
        }
        if self.dm_permission is not None:
            data["dm_permission"] = self.dm_permission
        if self.default_member_permissions is not None:
            data["default_member_permissions"] = self.default_member_permissions
        if self.options is not None:
            data["options"] = [o.to_json() for o in self.options]
        return data
