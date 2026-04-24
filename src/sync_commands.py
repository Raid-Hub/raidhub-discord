from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

import httpx

from .manifest import build_command_manifest
from .config import get_settings


def _required(value: str, key: str) -> str:
    if value:
        return value
    raise RuntimeError(f"{key} is required")


async def main() -> int:
    settings = get_settings()
    app_id = _required(settings.discord_application_id, "DISCORD_APPLICATION_ID")
    guild_id = (settings.discord_guild_id or "").strip()
    raid_filter_choices: list[tuple[str, int]] = []
    manifest_url = f"{settings.raidhub_api_base_url.rstrip('/')}/manifest"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            headers: dict[str, str] = {}
            if settings.raidhub_api_key:
                headers["x-api-key"] = settings.raidhub_api_key
            resp = await client.get(manifest_url, headers=headers)
            if resp.is_success:
                env = resp.json()
                inner = env.get("response") if isinstance(env, dict) else None
                if isinstance(inner, dict):
                    raid_filter_choices = _extract_raid_filter_choices(inner)
            else:
                print(
                    f"Warning: could not fetch raid choices from {manifest_url} "
                    f"({resp.status_code}). Continuing without raid dropdown choices.",
                    file=sys.stderr,
                )
    except Exception as err:
        print(
            f"Warning: failed to fetch raid choices from {manifest_url}: {err}. "
            "Continuing without raid dropdown choices.",
            file=sys.stderr,
        )

    payload = build_command_manifest(raid_filter_choices=raid_filter_choices)
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


def _extract_raid_filter_choices(manifest_response: dict[str, Any]) -> list[tuple[str, int]]:
    listed_ids = manifest_response.get("listedRaidIds") or []
    activity_defs = manifest_response.get("activityDefinitions") or {}
    if not isinstance(listed_ids, list) or not isinstance(activity_defs, dict):
        return []
    out: list[tuple[str, int]] = []
    for rid in listed_ids:
        key = str(rid)
        row = activity_defs.get(key)
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        if not isinstance(rid, int):
            continue
        out.append((name, rid))
        if len(out) >= 25:
            break
    return out


if __name__ == "__main__":
    raise SystemExit(cli())
