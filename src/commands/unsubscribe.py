from __future__ import annotations

from typing import Any

from ..config import Settings
from ..prom_metrics import observe_deferred_completion
from ..raidhub_client import RaidHubClient, discord_invocation_context
from .subscribe_resolution import (
    bungie_emblem_url,
    format_player_display_name,
    parse_clan_group_id,
    resolve_player_membership_id,
    resolve_player_subscription_row,
)
from .subscription_messages import (
    CLAN_ID_NOT_RECOGNIZED_TITLE,
    CLAN_UNSUBSCRIBED_TITLE,
    PLAYER_NOT_FOUND_TITLE,
    PLAYER_UNSUBSCRIBED_TITLE,
    SUBSCRIPTION_REMOVED_TITLE,
    UNSUBSCRIBE_CLAN_TITLE,
    UNSUBSCRIBE_COMMAND_TITLE,
    UNSUBSCRIBE_FAILED_TITLE,
    UNSUBSCRIBE_PLAYER_TITLE,
    unsubscribe_success_description,
)
from .subscription_helpers import (
    clan_put_targets_from_status,
    fetch_subscription_status_envelope,
    format_clan_display_name,
    player_put_targets_from_status,
    subscription_active_clan_ids,
    subscription_active_player_ids,
    subscription_envelope_error_message,
)
from .subscription_routes import SUB_ROUTE_DELETE, SUB_ROUTE_PUT
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


async def run_unsubscribe_deferred(
    interaction: dict[str, Any],
    raidhub: RaidHubClient,
    settings: Settings,
) -> None:
    app_id = application_id(interaction, settings)
    token = str(interaction.get("token") or "")
    data = interaction.get("data") or {}
    top_opts = data.get("options") or []
    sub = ""
    if top_opts and isinstance(top_opts[0], dict):
        sub = str(top_opts[0].get("name") or "").strip().lower()
    if not sub:
        sub = "all"
    if sub == "player":
        await run_unsubscribe_player_deferred(interaction, raidhub, settings)
        return
    if sub == "clan":
        await run_unsubscribe_clan_deferred(interaction, raidhub, settings)
        return

    outcome = "completed"
    try:
        if sub != "all":
            await patch_discord_followup_best_effort(
                app_id,
                token,
                warn_embed(
                    UNSUBSCRIBE_COMMAND_TITLE,
                    "Use `/unsubscribe all`, `/unsubscribe player`, or `/unsubscribe clan`.",
                ),
            )
            return
        if not interaction.get("guild_id") or not interaction.get("channel_id"):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                warn_embed(
                    UNSUBSCRIBE_COMMAND_TITLE,
                    "Run `/unsubscribe all` in a server text channel, not a DM.",
                ),
            )
            return

        if not await require_manage_webhooks_or_warn(
            interaction, app_id=app_id, token=token, title=UNSUBSCRIBE_COMMAND_TITLE
        ):
            return

        ctx = discord_invocation_context(interaction, route_id=SUB_ROUTE_DELETE)
        env = await raidhub.request_envelope(
            "DELETE",
            "/subscriptions/discord/webhooks",
            discord_context=ctx,
        )
        if not env.get("success"):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                error_embed(
                    UNSUBSCRIBE_FAILED_TITLE,
                    subscription_envelope_error_message(env),
                ),
            )
            return

        await patch_discord_followup_best_effort(
            app_id,
            token,
            success_embed(
                SUBSCRIPTION_REMOVED_TITLE,
                "RaidHub alerts are now turned off for this channel.",
            ),
        )
    except Exception as err:
        outcome = "error"
        await report_deferred_exception(
            command="unsubscribe",
            log_key="UNSUBSCRIBE_DEFERRED_FAILED",
            err=err,
            discord_application_id=app_id,
            interaction_token=token,
            user_message_payload=error_embed(UNSUBSCRIBE_FAILED_TITLE, USER_FACING_GENERIC),
        )
    finally:
        observe_deferred_completion(command="unsubscribe", outcome=outcome)


async def run_unsubscribe_player_deferred(
    interaction: dict[str, Any],
    raidhub: RaidHubClient,
    settings: Settings,
) -> None:
    app_id = application_id(interaction, settings)
    token = str(interaction.get("token") or "")
    outcome = "completed"
    try:
        leaf = flatten_options((interaction.get("data") or {}).get("options"))
        target_raw = str(leaf.get("player") or "").strip()
        if not target_raw:
            await patch_discord_followup_best_effort(
                app_id,
                token,
                warn_embed(
                    UNSUBSCRIBE_PLAYER_TITLE,
                    "Provide a Destiny membership id or player search text.",
                ),
            )
            return

        if not interaction.get("guild_id") or not interaction.get("channel_id"):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                warn_embed(
                    UNSUBSCRIBE_PLAYER_TITLE,
                    "Run this command in a server text channel, not a DM.",
                ),
            )
            return

        if not await require_manage_webhooks_or_warn(
            interaction, app_id=app_id, token=token, title=UNSUBSCRIBE_PLAYER_TITLE
        ):
            return

        prow = await resolve_player_subscription_row(raidhub, target_raw)
        if not prow:
            await patch_discord_followup_best_effort(
                app_id,
                token,
                error_embed(
                    PLAYER_NOT_FOUND_TITLE,
                    "Could not resolve that player. Try a membership id or a clearer name.",
                ),
            )
            return
        resolved_id = await resolve_player_membership_id(raidhub, target_raw) or ""
        if not resolved_id or not resolved_id.isdigit():
            await patch_discord_followup_best_effort(
                app_id,
                token,
                error_embed(PLAYER_NOT_FOUND_TITLE, "Missing membership id for that player."),
            )
            return

        status_env = await fetch_subscription_status_envelope(raidhub, interaction)
        if not status_env.get("success"):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                error_embed(
                    UNSUBSCRIBE_FAILED_TITLE,
                    subscription_envelope_error_message(status_env),
                ),
            )
            return
        inner = status_env.get("response") or {}
        if not inner.get("registered"):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                warn_embed(
                    UNSUBSCRIBE_PLAYER_TITLE,
                    "This channel has no RaidHub subscription to update.",
                ),
            )
            return

        players = subscription_active_player_ids(inner)
        if resolved_id not in players:
            await patch_discord_followup_best_effort(
                app_id,
                token,
                warn_embed(
                    UNSUBSCRIBE_PLAYER_TITLE,
                    f"This channel is not subscribed to player `{resolved_id}`.",
                ),
            )
            return

        row_list = player_put_targets_from_status(inner)
        next_rows = [r for r in row_list if r["membershipId"] != resolved_id]
        body: dict[str, Any] = {"targets": {"players": next_rows}}

        ctx = discord_invocation_context(interaction, route_id=SUB_ROUTE_PUT)
        env = await raidhub.request_envelope(
            "PUT",
            "/subscriptions/discord/webhooks",
            json=body,
            discord_context=ctx,
        )
        if not env.get("success"):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                error_embed(
                    UNSUBSCRIBE_FAILED_TITLE,
                    subscription_envelope_error_message(env),
                ),
            )
            return

        await patch_discord_followup_best_effort(
            app_id,
            token,
            success_embed(
                PLAYER_UNSUBSCRIBED_TITLE,
                unsubscribe_success_description(
                    format_player_display_name(prow),
                    resolved_id,
                ),
                thumbnail_url=bungie_emblem_url(str(prow.get("iconPath") or "")),
            ),
        )
    except Exception as err:
        outcome = "error"
        await report_deferred_exception(
            command="unsubscribe-player",
            log_key="UNSUBSCRIBE_PLAYER_DEFERRED_FAILED",
            err=err,
            discord_application_id=app_id,
            interaction_token=token,
            user_message_payload=error_embed(UNSUBSCRIBE_FAILED_TITLE, USER_FACING_GENERIC),
        )
    finally:
        observe_deferred_completion(command="unsubscribe-player", outcome=outcome)


async def run_unsubscribe_clan_deferred(
    interaction: dict[str, Any],
    raidhub: RaidHubClient,
    settings: Settings,
) -> None:
    app_id = application_id(interaction, settings)
    token = str(interaction.get("token") or "")
    outcome = "completed"
    try:
        leaf = flatten_options((interaction.get("data") or {}).get("options"))
        target_raw = str(leaf.get("clan") or "").strip()
        if not target_raw:
            await patch_discord_followup_best_effort(
                app_id,
                token,
                warn_embed(
                    UNSUBSCRIBE_CLAN_TITLE,
                    "Provide a clan group id or clan URL.",
                ),
            )
            return

        if not interaction.get("guild_id") or not interaction.get("channel_id"):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                warn_embed(
                    UNSUBSCRIBE_CLAN_TITLE,
                    "Run this command in a server text channel, not a DM.",
                ),
            )
            return

        if not await require_manage_webhooks_or_warn(
            interaction, app_id=app_id, token=token, title=UNSUBSCRIBE_CLAN_TITLE
        ):
            return

        gid = parse_clan_group_id(target_raw)
        if not gid:
            await patch_discord_followup_best_effort(
                app_id,
                token,
                error_embed(
                    CLAN_ID_NOT_RECOGNIZED_TITLE,
                    "Could not parse a clan group id from that value.",
                ),
            )
            return
        resolved_id = str(int(gid))

        status_env = await fetch_subscription_status_envelope(raidhub, interaction)
        if not status_env.get("success"):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                error_embed(
                    UNSUBSCRIBE_FAILED_TITLE,
                    subscription_envelope_error_message(status_env),
                ),
            )
            return
        inner = status_env.get("response") or {}
        if not inner.get("registered"):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                warn_embed(
                    UNSUBSCRIBE_CLAN_TITLE,
                    "This channel has no RaidHub subscription to update.",
                ),
            )
            return

        clans = subscription_active_clan_ids(inner)
        if resolved_id not in clans:
            await patch_discord_followup_best_effort(
                app_id,
                token,
                warn_embed(
                    UNSUBSCRIBE_CLAN_TITLE,
                    f"This channel is not subscribed to clan `{resolved_id}`.",
                ),
            )
            return

        row_list = clan_put_targets_from_status(inner)
        next_rows = [r for r in row_list if r["groupId"] != resolved_id]
        body = {"targets": {"clans": next_rows}}

        ctx = discord_invocation_context(interaction, route_id=SUB_ROUTE_PUT)
        env = await raidhub.request_envelope(
            "PUT",
            "/subscriptions/discord/webhooks",
            json=body,
            discord_context=ctx,
        )
        if not env.get("success"):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                error_embed(
                    UNSUBSCRIBE_FAILED_TITLE,
                    subscription_envelope_error_message(env),
                ),
            )
            return

        c_env = await raidhub.request_envelope("GET", f"/clan/{resolved_id}/basic")
        clan_row: dict[str, Any] = {}
        if c_env.get("success") and isinstance(c_env.get("response"), dict):
            clan_row = c_env["response"]
        c_disp = format_clan_display_name(clan_row) if clan_row else f"Clan `{resolved_id}`"
        c_thumb = (
            bungie_emblem_url(str(clan_row.get("avatarPath") or "")) if clan_row else None
        )

        await patch_discord_followup_best_effort(
            app_id,
            token,
            success_embed(
                CLAN_UNSUBSCRIBED_TITLE,
                unsubscribe_success_description(c_disp, resolved_id),
                thumbnail_url=c_thumb,
            ),
        )
    except Exception as err:
        outcome = "error"
        await report_deferred_exception(
            command="unsubscribe-clan",
            log_key="UNSUBSCRIBE_CLAN_DEFERRED_FAILED",
            err=err,
            discord_application_id=app_id,
            interaction_token=token,
            user_message_payload=error_embed(UNSUBSCRIBE_FAILED_TITLE, USER_FACING_GENERIC),
        )
    finally:
        observe_deferred_completion(command="unsubscribe-clan", outcome=outcome)


__all__ = [
    "run_unsubscribe_clan_deferred",
    "run_unsubscribe_deferred",
    "run_unsubscribe_player_deferred",
]
