from __future__ import annotations

from typing import Any

from ..config import Settings
from ..prom_metrics import observe_deferred_completion
from ..raidhub_client import RaidHubClient, discord_invocation_context
from .subscription_helpers import subscription_envelope_error_message
from .subscription_routes import SUB_ROUTE_DELETE
from .shared import (
    USER_FACING_GENERIC,
    application_id,
    error_embed,
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


__all__ = ["run_unsubscribe_deferred"]
