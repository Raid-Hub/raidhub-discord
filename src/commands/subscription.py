from __future__ import annotations

from typing import Any

from ..config import Settings
from ..prom_metrics import observe_deferred_completion
from ..raidhub_client import RaidHubClient, discord_invocation_context
from .subscription_messages import (
    SUBSCRIPTION_COMMAND_TITLE,
    SUBSCRIPTION_REMOVED_TITLE,
    SUBSCRIPTION_REQUEST_FAILED_TITLE,
)
from .subscription_helpers import (
    format_subscription_status_embed,
    subscription_envelope_error_message,
)
from .subscription_routes import SUB_ROUTE_DELETE, SUB_ROUTE_STATUS
from .shared import (
    USER_FACING_GENERIC,
    application_id,
    error_embed,
    patch_discord_followup_best_effort,
    report_deferred_exception,
    success_embed,
    warn_embed,
)


async def run_subscription_deferred(
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
                    SUBSCRIPTION_COMMAND_TITLE,
                    "Pick `status` or `delete` under `/subscription`.",
                ),
            )
            return

        sub = str(top_opts[0].get("name") or "").strip().lower()
        if sub not in ("delete", "status"):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                warn_embed(
                    SUBSCRIPTION_COMMAND_TITLE,
                    "Unknown `/subscription` subcommand.",
                ),
            )
            return

        if not interaction.get("guild_id") or not interaction.get("channel_id"):
            await patch_discord_followup_best_effort(
                app_id,
                token,
                warn_embed(
                    SUBSCRIPTION_COMMAND_TITLE,
                    "Run this command in a server channel, not a DM.",
                ),
            )
            return

        route_id = {"delete": SUB_ROUTE_DELETE, "status": SUB_ROUTE_STATUS}[sub]
        ctx = discord_invocation_context(interaction, route_id=route_id)

        if sub == "status":
            env = await raidhub.request_envelope(
                "GET",
                "/subscriptions/discord/webhooks",
                discord_context=ctx,
            )
        else:
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
                    SUBSCRIPTION_REQUEST_FAILED_TITLE,
                    subscription_envelope_error_message(env),
                ),
            )
            return

        inner = env.get("response") or {}
        if sub == "status":
            msg = await format_subscription_status_embed(raidhub, inner)
        else:
            msg = success_embed(
                SUBSCRIPTION_REMOVED_TITLE,
                "RaidHub will no longer use a webhook in this channel.",
            )

        await patch_discord_followup_best_effort(app_id, token, msg)
    except Exception as err:
        outcome = "error"
        await report_deferred_exception(
            command="subscription",
            log_key="SUBSCRIPTION_DEFERRED_FAILED",
            err=err,
            discord_application_id=app_id,
            interaction_token=token,
            user_message_payload=error_embed("Subscription Failed", USER_FACING_GENERIC),
        )
    finally:
        observe_deferred_completion(command="subscription", outcome=outcome)


__all__ = ["run_subscription_deferred"]
