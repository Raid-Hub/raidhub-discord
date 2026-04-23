from .builders import build_commands


def build_command_manifest() -> list[dict]:
    return [c.to_json() for c in build_commands()]


__all__ = ["build_command_manifest", "build_commands"]
