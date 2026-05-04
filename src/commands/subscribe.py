"""
`/subscribe` command: resolve clan URLs / player names, then register webhook targets.
"""

from __future__ import annotations

from typing import Any

from ..config import Settings
from ..prom_metrics import observe_deferred_completion
from ..raidhub_client import RaidHubClient, discord_invocation_context
from .subscribe_resolution import (
    bungie_emblem_url,
    format_player_display_name,
    parse_clan_group_id,
    resolve_player_subscription_row,
)
from .subscription_messages import (
    CLAN_ID_NOT_RECOGNIZED_TITLE,
    PLAYER_NOT_FOUND_TITLE,
    SUBSCRIBE_COMMAND_TITLE,
    SUBSCRIBE_FAILED_TITLE,
    SUBSCRIPTION_SAVED_TITLE,
    subscribe_success_description,
)
from .subscription_helpers import (
    clan_target_from_subscribe_leaf,
    fetch_subscription_status_envelope,
    format_clan_display_name,
    merge_clan_subscribe_put_body,
    merge_player_subscribe_put_body,
    player_target_from_subscribe_leaf,
    subscription_envelope_error_message,
)
from .subscription_routes import SUB_ROUTE_PUT, SUBSCRIPTION_WEBHOOKS_PATH
from .shared import (
    USER_FACING_GENERIC,
    application_id,
    error_embed,
    flatten_options,
    patch_discord_followup_best_effort,
    report_deferred_exception,
    require_manage_webhooks_or_warn,
    success_embed,
    warn_embed,
)


async def run_subscribe_deferred(
    interaction: dict[str, Any],
    raidhub: RaidHubClient,
    settings: Settings,
) -> None:
    app_id = application_id(interaction, settings)
    token = str(interaction.get("token") or "")
    outcome = "completed"
    try:
        data = interaction.get("data") or {}
        top_opts = data.get("options") or []
        if not top_opts or not isinstance(top_opts[0], dict):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                warn_embed(
                    SUBSCRIBE_COMMAND_TITLE,
                    "Use `/subscribe player` or `/subscribe clan` with a target.",
                ),
            )
            return

        sub = str(top_opts[0].get("name") or "").strip().lower()
        if sub not in ("player", "clan"):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                warn_embed(SUBSCRIBE_COMMAND_TITLE, "Unknown `/subscribe` subcommand."),
            )
            return

        leaf = flatten_options(top_opts[0].get("options"))
        target_raw = str(leaf.get("player") or leaf.get("clan") or "").strip()
        # TODO: Add raid filter input once we have a solid multi-select UX.
        if not target_raw:
            await patch_discord_followup_best_effort(
                app_id,
                token,
                warn_embed(
                    SUBSCRIBE_COMMAND_TITLE,
                    "Provide a target (membership id / player name, or clan id / URL).",
                ),
            )
            return

        if not interaction.get("guild_id") or not interaction.get("channel_id"):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                warn_embed(
                    SUBSCRIBE_COMMAND_TITLE,
                    "Run `/subscribe` in a server text channel, not a DM.",
                ),
            )
            return

        if not await require_manage_webhooks_or_warn(
            interaction, app_id=app_id, token=token, title=SUBSCRIBE_COMMAND_TITLE
        ):
            return

        status_env = await fetch_subscription_status_envelope(raidhub, interaction)
        if not status_env.get("success"):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                error_embed(
                    SUBSCRIBE_FAILED_TITLE,
                    subscription_envelope_error_message(status_env),
                ),
            )
            return
        status_inner = status_env.get("response") or {}
        registered = bool(status_inner.get("registered"))

        if sub == "player":
            prow = await resolve_player_subscription_row(raidhub, target_raw)
            if not prow:
                await patch_discord_followup_best_effort(
                    app_id,
                    token,
                    error_embed(
                        PLAYER_NOT_FOUND_TITLE,
                        "Could not resolve that player. Try a Destiny membership id or a clearer"
                        " name (first RaidHub search hit is used).",
                    ),
                )
                return
            raw_mid = prow.get("membershipId")
            try:
                resolved_id = str(int(str(raw_mid).strip())) if raw_mid is not None else ""
            except (TypeError, ValueError):
                resolved_id = ""
            if not resolved_id or not resolved_id.isdigit():
                await patch_discord_followup_best_effort(
                    app_id,
                    token,
                    error_embed(
                        PLAYER_NOT_FOUND_TITLE,
                        "Missing membership id for that player.",
                    ),
                )
                return
            if registered:
                body = merge_player_subscribe_put_body(status_inner, resolved_id, leaf)
            else:
                body = {
                    "targets": {
                        "players": [player_target_from_subscribe_leaf(resolved_id, leaf)]
                    }
                }
            display_name = format_player_display_name(prow)
            icon_raw = prow.get("iconPath")
            thumb_url = (
                bungie_emblem_url(str(icon_raw))
                if isinstance(icon_raw, str)
                else bungie_emblem_url(None)
            )
        else:
            gid = parse_clan_group_id(target_raw)
            if not gid:
                await patch_discord_followup_best_effort(
                    app_id,
                    token,
                    error_embed(
                        CLAN_ID_NOT_RECOGNIZED_TITLE,
                        "Could not parse a clan group id from that value. Use digits only, or a"
                        " raidhub.io/clan/... / Bungie clan URL containing the group id.",
                    ),
                )
                return
            resolved_id = str(int(gid))
            if registered:
                body = merge_clan_subscribe_put_body(status_inner, resolved_id, leaf)
            else:
                body = {
                    "targets": {"clans": [clan_target_from_subscribe_leaf(resolved_id, leaf)]}
                }

        ctx = discord_invocation_context(interaction, route_id=SUB_ROUTE_PUT)
        env = await raidhub.request_envelope(
            "PUT",
            SUBSCRIPTION_WEBHOOKS_PATH,
            json=body,
            discord_context=ctx,
        )

        if not env.get("success"):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                error_embed(
                    SUBSCRIBE_FAILED_TITLE,
                    subscription_envelope_error_message(env),
                ),
            )
            return

        if sub == "player":
            desc = subscribe_success_description(
                display_name,
                resolved_id,
                str(interaction.get("channel_id") or ""),
            )
            msg = success_embed(
                SUBSCRIPTION_SAVED_TITLE,
                desc,
                thumbnail_url=thumb_url,
            )
        else:
            c_env = await raidhub.request_envelope("GET", f"/clan/{resolved_id}/basic")
            clan_row: dict[str, Any] = {}
            if c_env.get("success") and isinstance(c_env.get("response"), dict):
                clan_row = c_env["response"]
            c_disp = (
                format_clan_display_name(clan_row) if clan_row else f"Clan `{resolved_id}`"
            )
            apath = clan_row.get("avatarPath")
            c_thumb = (
                bungie_emblem_url(str(apath))
                if clan_row and isinstance(apath, str)
                else None
            )
            desc = subscribe_success_description(
                c_disp,
                resolved_id,
                str(interaction.get("channel_id") or ""),
            )
            msg = success_embed(
                SUBSCRIPTION_SAVED_TITLE,
                desc,
                thumbnail_url=c_thumb,
            )
        await patch_discord_followup_best_effort(app_id, token, msg)
    except Exception as err:
        outcome = "error"
        await report_deferred_exception(
            command="subscribe",
            log_key="SUBSCRIBE_DEFERRED_FAILED",
            err=err,
            discord_application_id=app_id,
            interaction_token=token,
            user_message_payload=error_embed(SUBSCRIBE_FAILED_TITLE, USER_FACING_GENERIC),
        )
    finally:
        observe_deferred_completion(command="subscribe", outcome=outcome)


__all__ = ["run_subscribe_deferred", "parse_clan_group_id"]
