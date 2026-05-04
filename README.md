# raidhub-discord

Backend for the RaidHub Discord application: it receives [Discord interactions](https://discord.com/developers/docs/interactions/receiving-and-responding) over HTTP, checks request signatures, registers slash commands, and proxies the relevant work to the RaidHub API (search, channel subscriptions, and related flows). It is meant to run as a small always-on service (for example behind your ingress), not as something you embed in other apps.

## Quick start

1. Copy `.env.example` to `.env` and set Discord and RaidHub values there. Use an API base URL this process can actually reach (a cloud-hosted bot cannot call `http://localhost:8000` on your laptop).
2. Use Python **3.14+**, create a virtualenv, then `pip install -e ".[dev]"` from this directory.
3. Run the app, for example: `uvicorn src.main:app --reload --port 8787` (use the same interpreter you installed into).

When the RaidHub API runs with production-style auth, configure the API key in `.env` to match what the API expects (see comments in `.env.example`).

## Linked-account cache (Redis)

If `RAIDHUB_ACCOUNT_TURSO_URL` is set, Discord user → Bungie / Destiny profile resolution is cached in **Redis** using the same connection style as RaidHub-Services (`REDIS_HOST` / `REDIS_PORT` / optional `REDIS_PASSWORD`, or `REDIS_URL`). TTL defaults to 90s (`RAIDHUB_ACCOUNT_LOOKUP_CACHE_TTL_SECONDS`).

**Bust cache:** increment `RAIDHUB_DISCORD_LINKED_ACCOUNT_CACHE_NS` (e.g. `1` → `2`), or delete keys under `raidhub:discord:linked:<ns>:*` (prefer `SCAN` in production). If Redis is not configured, lookups always hit Turso.

**User JWT (scoped API):** with `RAIDHUB_CLIENT_SECRET` set (same as RaidHub-API `CLIENT_SECRET`), linked users get a short-lived cached **user JWT** via `POST /authorize/user`; outbound calls send it as `x-raidhub-user-authorization: Bearer …` alongside `Authorization: Discord …` where used (e.g. `/search`).

**Slash `/link` and `/register`:** ephemeral prompt with a button to `RAIDHUB_WEBSITE_BASE_URL/account` (default `https://raidhub.io`).

## Slash command sync

After changing command definitions, push them to Discord with the `sync-discord-commands` console script from this package.

- Leave `DISCORD_GUILD_ID` unset for **global** commands (slower to propagate everywhere).
- Set `DISCORD_GUILD_ID` for **guild** commands while iterating (updates show up quickly in that server).
- Set `DISCORD_SYNC_DRY_RUN=true` to print the payload without calling Discord.

## Observability (optional)

Logging level is controlled with `LOG_LEVEL`. You can point `SENTRY_DSN` (and related `SENTRY_*` variables) at Sentry for error reporting; see `.env.example` for the full set.
