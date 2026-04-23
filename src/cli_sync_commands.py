from __future__ import annotations


def cli() -> int:
    from src.sync_commands import cli as sync_cli

    return sync_cli()
