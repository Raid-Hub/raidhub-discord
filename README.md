# raidhub-discord

Python Discord ingress service for RaidHub.

## Setup

1. Copy `.env.example` to `.env` and fill required values. For local RaidHub API with `PROD=true`, add the same key to `RaidHub-API/api-keys.json` (see `api-keys.example.json`) and set `RAIDHUB_API_KEY` here to match.
2. Create a venv (Python 3.14+) and install:
   - `/usr/local/opt/python@3.14/bin/python3.14 -m venv .venv`
   - `.venv/bin/python -m pip install --upgrade pip`
   - `.venv/bin/python -m pip install -e ".[dev]"`
3. Run **using that interpreter** (otherwise you get `ModuleNotFoundError: No module named 'jwt'` — PyJWT is only installed in the venv):
   - `.venv/bin/uvicorn src.main:app --reload --port 8787`

## Sync commands

- Global sync:
  - `sync-discord-commands`
- Guild sync (faster propagation):
  - set `DISCORD_GUILD_ID` in `.env`, then run `sync-discord-commands`
- Dry run:
  - set `DISCORD_SYNC_DRY_RUN=true`

## Notes

- Logging: import a subsystem logger from `src/log.py` (`ingress`, `raidhub_api`, `pagination`, `handlers`) — do not construct `Logger` outside that file. Implementation is `src/structured_logger.py` (same line shape as RaidHub-Services: `{ISO8601} [LEVEL][PREFIX] -- LOG_KEY >> k=v`), uppercase event keys, optional `LOG_LEVEL` (`debug` / `info` / `warn` / `error`).
- Interaction callback numeric types come from Discord’s official [`discord-interactions`](https://pypi.org/project/discord-interactions/) package (`InteractionType`, `InteractionResponseType`). Command/component option types use `src/discord_v10_enums.py` (mirrors API v10; there is no small third-party package that covers every enum).
- `/interactions` verifies Discord signatures.
- RaidHub API calls send `x-api-key` when `RAIDHUB_API_KEY` is set (required when the API runs with `PROD=true`).
- Optional `Authorization: Discord <signed-jwt>` uses `RAIDHUB_JWT_SECRET` (same value as RaidHub `JWT_SECRET` if you sign Discord-context payloads).
- Slash commands **`player-search`** and **`instance`** call the RaidHub API (`GET /player/search`, `GET /instance/:id`), defer the interaction, then PATCH the follow-up message.
- **Discord vs RaidHub errors:** Discord’s **POST `/interactions`** must return **HTTP 2xx** within a few seconds (this app usually responds with deferred `type: 5` first). You cannot retroactively change that to 504 after deferring. When RaidHub returns **HTTP 5xx**, `request_envelope` maps to `RaidHubApiServerError` and the **PATCH** to `@original` uses a short user-facing message (no raw URLs, tokens, or stack traces). Discord **PATCH** failures (e.g. 400 invalid form body) are logged with response body; users see a generic “could not update” line only.
- **Pagination:** `src/pagination/` stores session state and dispatches `prefix:session_id:nav_token`. Offset rows from `build_pager_action_row` use **`p{n}` / `n{n}`** tokens (unique `custom_id`s even for one page); decode with `parse_offset_page_nav_token`. Use `build_dual_nav_action_row` for arbitrary cursor/action tokens. Single-process unless you replace the store.
