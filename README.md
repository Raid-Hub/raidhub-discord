# raidhub-discord

Backend for the RaidHub Discord application: it receives [Discord interactions](https://discord.com/developers/docs/interactions/receiving-and-responding) over HTTP, checks request signatures, registers slash commands, and proxies the relevant work to the RaidHub API (search, instances, channel subscriptions, and related flows). It is meant to run as a small always-on service (for example behind your ingress), not as something you embed in other apps.

## Quick start

1. Copy `.env.example` to `.env` and set Discord and RaidHub values there. Use an API base URL this process can actually reach (a cloud-hosted bot cannot call `http://localhost:8000` on your laptop).
2. Use Python **3.14+**, create a virtualenv, then `pip install -e ".[dev]"` from this directory.
3. Run the app, for example: `uvicorn src.main:app --reload --port 8787` (use the same interpreter you installed into).

When the RaidHub API runs with production-style auth, configure the API key in `.env` to match what the API expects (see comments in `.env.example`).

## Slash command sync

After changing command definitions, push them to Discord with the `sync-discord-commands` console script from this package.

- Leave `DISCORD_GUILD_ID` unset for **global** commands (slower to propagate everywhere).
- Set `DISCORD_GUILD_ID` for **guild** commands while iterating (updates show up quickly in that server).
- Set `DISCORD_SYNC_DRY_RUN=true` to print the payload without calling Discord.

## Observability (optional)

Logging level is controlled with `LOG_LEVEL`. You can point `SENTRY_DSN` (and related `SENTRY_*` variables) at Sentry for error reporting; see `.env.example` for the full set.
