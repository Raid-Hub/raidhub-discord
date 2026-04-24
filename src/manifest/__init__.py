from .builders import build_commands


def build_command_manifest(raid_filter_choices: list[tuple[str, int]] | None = None) -> list[dict]:
    return [c.to_json() for c in build_commands(raid_filter_choices=raid_filter_choices)]


__all__ = ["build_command_manifest", "build_commands"]
