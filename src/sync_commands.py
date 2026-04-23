from __future__ import annotations

import asyncio
import json
import sys

import httpx

from .command_manifest import build_command_manifest
from .config import get_settings


def _required(value: str, key: str) -> str:
    if value:
        return value
    raise RuntimeError(f"{key} is required")


async def main() -> int:
    settings = get_settings()
    app_id = _required(settings.discord_application_id, "DISCORD_APPLICATION_ID")
    guild_id = (settings.discord_guild_id or "").strip()

    payload = build_command_manifest()
    if guild_id:
        endpoint = (
            f"https://discord.com/api/v10/applications/{app_id}/guilds/{guild_id}/commands"
        )
        scope = f"guild:{guild_id}"
    else:
        endpoint = f"https://discord.com/api/v10/applications/{app_id}/commands"
        scope = "global"

    if settings.discord_sync_dry_run:
        print(
            json.dumps(
                {
                    "target": scope,
                    "endpoint": endpoint,
                    "commands": payload,
                },
                indent=2,
            )
        )
        return 0

    bot_token = _required(settings.discord_bot_token, "DISCORD_BOT_TOKEN")

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.put(
            endpoint,
            headers={
                "Authorization": f"Bot {bot_token}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if response.status_code >= 400:
        detail = response.text
        print(f"Discord command sync failed ({response.status_code}): {detail}", file=sys.stderr)
        return 1

    print(f"Synced {len(payload)} Discord command(s) to {scope} scope.")
    return 0


def cli() -> int:
    return asyncio.run(main())


if __name__ == "__main__":
    raise SystemExit(cli())
