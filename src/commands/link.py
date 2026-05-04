from __future__ import annotations

from typing import Any

from discord_interactions import InteractionResponseType

from ..config import Settings


def link_interaction_response(settings: Settings) -> dict[str, Any]:
    """Ephemeral message + link button to RaidHub account (and optional docs)."""
    base = settings.raidhub_website_base_url.rstrip("/")
    account_url = f"{base}/account"
    desc = (
        "1. Open **RaidHub account** below (Bungie sign-in if asked).\n"
        "2. Under **Linked accounts**, connect **Discord** and approve **linked roles** scopes.\n"
        "3. Return here — slash commands can then use your RaidHub identity (when the bot is configured with `RAIDHUB_CLIENT_SECRET`)."
    )
    return {
        "type": InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
        "data": {
            "flags": 64,
            "embeds": [
                {
                    "title": "Link RaidHub ↔ Discord",
                    "description": desc[:4096],
                    "color": 0x5865_F2,
                }
            ],
            "components": [
                {
                    "type": 1,
                    "components": [
                        {
                            "type": 2,
                            "style": 5,
                            "label": "Open RaidHub account",
                            "url": account_url[:512],
                        }
                    ],
                }
            ],
        },
    }
