from __future__ import annotations

from typing import Any

from ..config import Settings
from ..prom_metrics import observe_deferred_completion
from ..raidhub_client import RaidHubClient, discord_invocation_context
from .subscribe_resolution import parse_clan_group_id, resolve_player_membership_id
from .subscription_helpers import (
    fetch_subscription_status_envelope,
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
    outcome = "completed"
    try:
        if not interaction.get("guild_id") or not interaction.get("channel_id"):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                warn_embed(
                    "Unsubscribe Command",
                    "Run `/unsubscribe` in a server text channel, not a DM.",
                ),
            )
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
                    "Unsubscribe Failed",
                    subscription_envelope_error_message(env),
                ),
            )
            return

        await patch_discord_followup_best_effort(
            app_id,
            token,
            success_embed(
                "Subscription Removed",
                "RaidHub will no longer use a webhook in this channel.",
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
            user_message_payload=error_embed("Unsubscribe Failed", USER_FACING_GENERIC),
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
                    "Unsubscribe Player",
                    "Provide a Destiny membership id or player search text.",
                ),
            )
            return

        if not interaction.get("guild_id") or not interaction.get("channel_id"):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                warn_embed(
                    "Unsubscribe Player",
                    "Run this command in a server text channel, not a DM.",
                ),
            )
            return

        resolved_id = await resolve_player_membership_id(raidhub, target_raw)
        if not resolved_id:
            await patch_discord_followup_best_effort(
                app_id,
                token,
                error_embed(
                    "Player Not Found",
                    "Could not resolve that player. Try a membership id or a clearer name.",
                ),
            )
            return

        status_env = await fetch_subscription_status_envelope(raidhub, interaction)
        if not status_env.get("success"):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                error_embed(
                    "Unsubscribe Failed",
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
                    "Unsubscribe Player",
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
                    "Unsubscribe Player",
                    f"This channel is not subscribed to player `{resolved_id}`.",
                ),
            )
            return

        next_players = sorted([p for p in players if p != resolved_id])
        body: dict[str, Any] = {"targets": {"playerMembershipIds": next_players}}

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
                    "Unsubscribe Failed",
                    subscription_envelope_error_message(env),
                ),
            )
            return

        await patch_discord_followup_best_effort(
            app_id,
            token,
            success_embed(
                "Player Unsubscribed",
                f"Removed player `{resolved_id}` from this channel. Other subscription rules are"
                " unchanged.",
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
            user_message_payload=error_embed("Unsubscribe Failed", USER_FACING_GENERIC),
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
                    "Unsubscribe Clan",
                    "Provide a clan group id or clan URL.",
                ),
            )
            return

        if not interaction.get("guild_id") or not interaction.get("channel_id"):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                warn_embed(
                    "Unsubscribe Clan",
                    "Run this command in a server text channel, not a DM.",
                ),
            )
            return

        gid = parse_clan_group_id(target_raw)
        if not gid:
            await patch_discord_followup_best_effort(
                app_id,
                token,
                error_embed(
                    "Clan ID Not Recognized",
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
                    "Unsubscribe Failed",
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
                    "Unsubscribe Clan",
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
                    "Unsubscribe Clan",
                    f"This channel is not subscribed to clan `{resolved_id}`.",
                ),
            )
            return

        next_clans = sorted([c for c in clans if c != resolved_id])
        body = {"targets": {"clanGroupIds": next_clans}}

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
                    "Unsubscribe Failed",
                    subscription_envelope_error_message(env),
                ),
            )
            return

        await patch_discord_followup_best_effort(
            app_id,
            token,
            success_embed(
                "Clan Unsubscribed",
                f"Removed clan `{resolved_id}` from this channel. Other subscription rules are"
                " unchanged.",
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
            user_message_payload=error_embed("Unsubscribe Failed", USER_FACING_GENERIC),
        )
    finally:
        observe_deferred_completion(command="unsubscribe-clan", outcome=outcome)


__all__ = [
    "run_unsubscribe_clan_deferred",
    "run_unsubscribe_deferred",
    "run_unsubscribe_player_deferred",
]
