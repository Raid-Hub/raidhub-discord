from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    port: int
    discord_public_key: str
    discord_application_id: str
    discord_bot_token: str
    discord_guild_id: str
    discord_sync_dry_run: bool
    raidhub_api_base_url: str
    raidhub_api_key: str
    raidhub_jwt_secret: str


def get_settings() -> Settings:
    return Settings(
        port=int(os.getenv("PORT", "8787")),
        discord_public_key=os.getenv("DISCORD_PUBLIC_KEY", "").strip(),
        discord_application_id=os.getenv("DISCORD_APPLICATION_ID", "").strip(),
        discord_bot_token=os.getenv("DISCORD_BOT_TOKEN", "").strip(),
        discord_guild_id=os.getenv("DISCORD_GUILD_ID", "").strip(),
        discord_sync_dry_run=os.getenv("DISCORD_SYNC_DRY_RUN", "false").strip().lower()
        == "true",
        raidhub_api_base_url=os.getenv(
            "RAIDHUB_API_BASE_URL", "http://localhost:8000"
        ).strip(),
        raidhub_api_key=os.getenv("RAIDHUB_API_KEY", "").strip(),
        raidhub_jwt_secret=os.getenv("RAIDHUB_JWT_SECRET", "").strip(),
    )
